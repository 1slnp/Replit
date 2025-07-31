import os
import uuid
import json
from flask import render_template, request, jsonify, redirect, url_for, flash, session, send_file
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from app import app, db
from models import User, CoverArt, VocalMaster, VideoGeneration
from openai_integration import generate_cover_art_image, generate_with_midjourney, generate_with_stable_diffusion, generate_with_dreamshaper, generate_with_playground, download_and_save_image, generate_video_with_runway, download_and_save_video, create_demo_video_with_audio
import stripe
import time
import random

# Allowed file extensions for audio uploads
ALLOWED_EXTENSIONS = {'mp3', 'wav', 'flac', 'm4a', 'aac'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/test_video_direct.html')
def test_video_direct():
    with open('test_video_direct.html', 'r') as f:
        return f.read()

@app.route('/test_complete_video.html')
def test_complete_video():
    with open('test_complete_video.html', 'r') as f:
        return f.read()

@app.route('/test_final_video.html')
def test_final_video():
    with open('test_final_video.html', 'r') as f:
        return f.read()

@app.route('/test_real_frontend.html')
def test_real_frontend():
    with open('test_real_frontend.html', 'r') as f:
        return f.read()

@app.route('/test_user_experience.html')
def test_user_experience():
    with open('test_user_experience.html', 'r') as f:
        return f.read()

@app.route('/test_downloads.html')
def test_downloads():
    with open('test_downloads.html', 'r') as f:
        return f.read()

@app.route('/test_user_workflow.html')
def test_user_workflow():
    with open('test_user_workflow.html', 'r') as f:
        return f.read()

@app.route('/cover-art')
def cover_art():
    # Get recent covers for demo (increased limit to show more)
    recent_covers = CoverArt.query.order_by(CoverArt.created_at.desc()).limit(10).all()
    return render_template('cover_art.html', recent_covers=recent_covers)

@app.route('/vocal-mastering')
def vocal_mastering():
    # Get recent jobs for demo
    recent_jobs = VocalMaster.query.order_by(VocalMaster.created_at.desc()).limit(5).all()
    return render_template('vocal_mastering.html', recent_jobs=recent_jobs)

@app.route('/video-generator')
def video_generator():
    # Get recent video jobs for demo
    recent_videos = VideoGeneration.query.order_by(VideoGeneration.created_at.desc()).limit(5).all()
    return render_template('video_generator.html', recent_videos=recent_videos)

@app.route('/api/generate-cover-art', methods=['POST'])
def generate_cover_art():
    try:
        data = request.get_json()
        artist_name = data.get('artist_name', '').strip()
        album_title = data.get('album_title', '').strip()
        genre = data.get('genre', '')
        explicit_content = data.get('explicit_content', False)
        ai_prompt = data.get('ai_prompt', '').strip()
        selectedModel = data.get('ai_model', data.get('model', 'dalle3'))

        # Validate required fields
        if not artist_name or not album_title or not genre:
            return jsonify({'error': 'Artist name, album title, and genre are required'}), 400

        # Check token balance
        if current_user.is_authenticated:
            current_tokens = current_user.tokens
        else:
            current_tokens = session.get('tokens', 2)
        
        if current_tokens <= 0:
            return jsonify({'error': 'Insufficient tokens. Please purchase more tokens.'}), 402

        # Generate AI image based on selected model
        image_result = None
        
        # Generate with selected AI model
        if selectedModel == "dalle3":
            image_result = generate_cover_art_image(ai_prompt, artist_name, album_title)
        elif selectedModel == "midjourney":
            image_result = generate_with_midjourney(ai_prompt, artist_name, album_title)
        elif selectedModel == "dreamshaper":
            image_result = generate_with_dreamshaper(ai_prompt, artist_name, album_title)
        elif selectedModel == "playground":
            image_result = generate_with_playground(ai_prompt, artist_name, album_title)
        else:  # stable-diffusion or default
            image_result = generate_with_stable_diffusion(ai_prompt, artist_name, album_title)
        
        if not image_result['success']:
            return jsonify({'error': f'AI image generation failed: {image_result["error"]}'}), 500

        # Handle image saving based on result type
        if 'image_url' in image_result and image_result['image_url'].startswith('http'):
            # Real AI generated image - download it
            image_filename = f"generated_{uuid.uuid4().hex[:8]}.jpg"
            try:
                local_image_path = download_and_save_image(image_result['image_url'], image_filename)
            except Exception as e:
                return jsonify({'error': f'Failed to save generated image: {str(e)}'}), 500
        else:
            # Fallback image - already saved locally
            image_filename = image_result['image_url'].split('/')[-1]

        # Create cover art record
        cover_art = CoverArt()
        cover_art.artist_name = artist_name
        cover_art.album_title = album_title
        cover_art.genre = genre
        cover_art.explicit_content = explicit_content
        cover_art.ai_prompt = ai_prompt
        cover_art.image_path = image_filename
        
        db.session.add(cover_art)
        db.session.commit()

        # Deduct token
        if current_user.is_authenticated:
            current_user.tokens = current_tokens - 1
            db.session.commit()
            tokens_remaining = current_user.tokens
        else:
            session['tokens'] = current_tokens - 1
            tokens_remaining = session['tokens']

        # Return success response with real generated image URL
        return jsonify({
            'success': True,
            'image_url': f'/static/images/generated/{image_filename}',
            'cover_id': cover_art.id,
            'tokens_remaining': tokens_remaining
        })

    except Exception as e:
        app.logger.error(f"Error generating cover art: {str(e)}")
        # Provide more specific error messages
        if "api key" in str(e).lower():
            return jsonify({'error': 'AI service not configured. Please contact support.'}), 500
        elif "quota" in str(e).lower() or "billing" in str(e).lower():
            return jsonify({'error': 'AI service temporarily unavailable. Please try again later.'}), 503
        else:
            return jsonify({'error': 'Artwork could not be generated. Check your prompt or try again.'}), 500

@app.route('/api/generate-prompt', methods=['POST'])
def generate_prompt():
    try:
        data = request.get_json()
        genre = data.get('genre', '')
        artist_name = data.get('artist_name', '')
        album_title = data.get('album_title', '')

        # Generate AI prompt based on inputs
        prompts = {
            'Hip Hop': [
                f"Urban street art style album cover for '{album_title}' by {artist_name}, bold graffiti elements, neon lighting, cityscape background",
                f"Modern hip-hop album artwork featuring {artist_name}, geometric patterns, gold and black color scheme, professional photography style",
                f"Street photography inspired cover for '{album_title}', urban environment, dramatic lighting, contemporary hip-hop aesthetic"
            ],
            'Pop': [
                f"Clean modern pop album cover for '{album_title}' by {artist_name}, minimalist design, pastel colors, professional studio lighting",
                f"Contemporary pop artwork featuring vibrant colors, geometric shapes, clean typography for {artist_name}",
                f"Sleek pop music cover design for '{album_title}', gradient backgrounds, modern aesthetic, commercial appeal"
            ],
            'R&B': [
                f"Smooth R&B album cover for '{album_title}' by {artist_name}, warm golden tones, intimate lighting, soulful aesthetic",
                f"Contemporary R&B artwork featuring {artist_name}, silk textures, sunset colors, emotional depth",
                f"Elegant R&B cover design for '{album_title}', smooth gradients, romantic atmosphere, sophisticated styling"
            ],
            'Indie': [
                f"Dreamy indie album cover for '{album_title}' by {artist_name}, film photography aesthetic, vintage filters, artistic composition",
                f"Alternative indie artwork featuring {artist_name}, ethereal lighting, natural elements, authentic storytelling",
                f"Artistic indie cover design for '{album_title}', retro colors, analog photography style, creative layout"
            ],
            'Rock': [
                f"Dramatic rock album cover for '{album_title}' by {artist_name}, bold typography, intense lighting, powerful imagery",
                f"Heavy rock artwork featuring {artist_name}, industrial elements, dark atmosphere, raw energy",
                f"Classic rock cover design for '{album_title}', electric energy, stage lighting, rebellious spirit"
            ],
            'Electronic': [
                f"Futuristic electronic album cover for '{album_title}' by {artist_name}, neon colors, digital effects, cyberpunk aesthetic",
                f"Modern electronic artwork featuring {artist_name}, holographic elements, bright colors, technological themes",
                f"Synthwave electronic cover design for '{album_title}', retro-futuristic style, electric blues and purples"
            ],
            'Jazz': [
                f"Vintage jazz album cover for '{album_title}' by {artist_name}, warm sepia tones, classic typography, timeless elegance",
                f"Sophisticated jazz artwork featuring {artist_name}, noir atmosphere, golden age styling, musical instruments",
                f"Classic jazz cover design for '{album_title}', rich textures, vintage aesthetic, soulful composition"
            ]
        }

        genre_prompts = prompts.get(genre, prompts['Pop'])
        selected_prompt = random.choice(genre_prompts)

        return jsonify({'prompt': selected_prompt})

    except Exception as e:
        app.logger.error(f"Error generating prompt: {str(e)}")
        return jsonify({'error': 'Failed to generate prompt'}), 500

@app.route('/api/upload-audio', methods=['POST'])
def upload_audio():
    try:
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400

        file = request.files['audio']
        track_title = request.form.get('track_title', '').strip()
        template = request.form.get('template', 'Radio Ready')

        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        if not track_title:
            return jsonify({'error': 'Track title is required'}), 400

        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file format. Supported formats: MP3, WAV, FLAC, M4A, AAC'}), 400

        # Check token balance
        if current_user.is_authenticated:
            current_tokens = current_user.tokens
        else:
            current_tokens = session.get('tokens', 2)
        
        if current_tokens <= 0:
            return jsonify({'error': 'Insufficient tokens. Please purchase more tokens.'}), 402

        # Save uploaded file
        if not file.filename:
            return jsonify({'error': 'Invalid file'}), 400
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)

        # Create vocal master record
        vocal_master = VocalMaster()
        vocal_master.track_title = track_title
        vocal_master.original_file = unique_filename
        vocal_master.template = template
        vocal_master.status = 'processing'

        db.session.add(vocal_master)
        db.session.commit()

        # Deduct token
        if current_user.is_authenticated:
            current_user.tokens = current_tokens - 1
            db.session.commit()
            tokens_remaining = current_user.tokens
        else:
            session['tokens'] = current_tokens - 1
            tokens_remaining = session['tokens']

        return jsonify({
            'success': True,
            'job_id': vocal_master.id,
            'message': 'File uploaded successfully. Processing will begin shortly.',
            'tokens_remaining': tokens_remaining
        })

    except Exception as e:
        app.logger.error(f"Error uploading audio: {str(e)}")
        return jsonify({'error': 'Failed to upload audio file'}), 500

@app.route('/api/upload-vocal', methods=['POST'])
def upload_vocal():
    """Upload vocal track for mastering"""
    try:
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400
        
        file = request.files['audio']
        track_title = request.form.get('track_title', '').strip()
        template = request.form.get('template', 'Radio Ready')
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not track_title:
            return jsonify({'error': 'Track title is required'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Please upload MP3, WAV, FLAC, M4A, or AAC files.'}), 400
        
        # Check token balance
        if current_user.is_authenticated:
            current_tokens = current_user.tokens
        else:
            current_tokens = session.get('tokens', 2)
        
        if current_tokens <= 0:
            return jsonify({'error': 'Insufficient tokens. Please purchase more tokens.'}), 402
        
        # Save uploaded file
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)
        
        # Create vocal master record
        vocal_master = VocalMaster()
        vocal_master.track_title = track_title
        vocal_master.original_file = unique_filename
        vocal_master.template = template
        vocal_master.status = 'uploaded'
        
        if current_user.is_authenticated:
            vocal_master.user_id = current_user.id
        
        db.session.add(vocal_master)
        db.session.commit()
        
        # Deduct token
        if current_user.is_authenticated:
            current_user.tokens -= 1
            db.session.commit()
        else:
            session['tokens'] = current_tokens - 1
        
        return jsonify({
            'success': True,
            'job_id': vocal_master.id,
            'message': 'Audio uploaded successfully',
            'remaining_tokens': current_user.tokens if current_user.is_authenticated else session['tokens']
        })
        
    except Exception as e:
        app.logger.error(f"Error uploading vocal: {str(e)}")
        return jsonify({'error': 'Failed to upload audio file'}), 500

@app.route('/api/start-mastering', methods=['POST'])
def start_mastering():
    try:
        data = request.get_json()
        job_id = data.get('job_id')
        eq_settings = data.get('eq_settings', {})

        vocal_master = VocalMaster.query.get(job_id)
        if not vocal_master:
            return jsonify({'error': 'Job not found'}), 404

        # Update EQ settings and start processing
        vocal_master.eq_settings = eq_settings
        vocal_master.status = 'processing'
        db.session.commit()

        # Simulate processing delay
        time.sleep(3)

        # Apply real audio mastering processing
        from audio_processor import apply_vocal_mastering
        
        original_path = os.path.join(app.config['UPLOAD_FOLDER'], vocal_master.original_file)
        mastered_filename = f"mastered_{vocal_master.original_file}"
        mastered_path = os.path.join(app.config['UPLOAD_FOLDER'], mastered_filename)
        
        # Apply template-specific audio processing
        template_settings = {
            'template': vocal_master.template,
            'eq_settings': eq_settings
        }
        
        success = apply_vocal_mastering(original_path, mastered_path, template_settings)
        if not success:
            return jsonify({'error': 'Audio processing failed'}), 500
        
        # Mark as completed
        vocal_master.status = 'completed'
        vocal_master.mastered_file = mastered_filename
        db.session.commit()

        return jsonify({
            'success': True,
            'status': 'completed',
            'original_audio_url': f'/audio/{vocal_master.id}/original',
            'mastered_audio_url': f'/audio/{vocal_master.id}/mastered'
        })

    except Exception as e:
        app.logger.error(f"Error starting mastering: {str(e)}")
        return jsonify({'error': 'Failed to start mastering process'}), 500

@app.route('/api/job-status/<int:job_id>')
def job_status(job_id):
    vocal_master = VocalMaster.query.get(job_id)
    if not vocal_master:
        return jsonify({'error': 'Job not found'}), 404

    return jsonify({
        'status': vocal_master.status,
        'track_title': vocal_master.track_title,
        'created_at': vocal_master.created_at.isoformat(),
        'original_url': f'/audio/{job_id}/original' if vocal_master.status == 'completed' else None,
        'mastered_url': f'/audio/{job_id}/mastered' if vocal_master.status == 'completed' else None
    })

# Audio serving routes for real-time playback
@app.route('/audio/<int:job_id>/original')
def serve_original_audio(job_id):
    """Serve original audio file for real-time comparison"""
    try:
        vocal_master = VocalMaster.query.get(job_id)
        if not vocal_master:
            return jsonify({'error': 'Job not found'}), 404
        
        original_path = os.path.join(app.config['UPLOAD_FOLDER'], vocal_master.original_file)
        if not os.path.exists(original_path):
            return jsonify({'error': 'Original audio file not found'}), 404
        
        return send_file(original_path, mimetype='audio/mpeg')
    except Exception as e:
        app.logger.error(f"Error serving original audio: {str(e)}")
        return jsonify({'error': 'Failed to serve audio'}), 500

@app.route('/audio/<int:job_id>/mastered')
def serve_mastered_audio(job_id):
    """Serve mastered audio file for real-time comparison"""
    try:
        vocal_master = VocalMaster.query.get(job_id)
        if not vocal_master or vocal_master.status != 'completed':
            return jsonify({'error': 'Mastered audio not ready'}), 404
        
        mastered_path = os.path.join(app.config['UPLOAD_FOLDER'], vocal_master.mastered_file)
        if not os.path.exists(mastered_path):
            return jsonify({'error': 'Mastered audio file not found'}), 404
        
        return send_file(mastered_path, mimetype='audio/mpeg')
    except Exception as e:
        app.logger.error(f"Error serving mastered audio: {str(e)}")
        return jsonify({'error': 'Failed to serve audio'}), 500

@app.route('/api/apply-realtime-eq', methods=['POST'])
def apply_realtime_eq():
    """Apply EQ changes in real-time without reprocessing the entire file"""
    try:
        data = request.get_json()
        job_id = data.get('job_id')
        template = data.get('template', 'Radio Ready')
        eq_settings = data.get('eq_settings', {})
        
        if not job_id:
            return jsonify({'error': 'Job ID is required'}), 400
        
        vocal_master = VocalMaster.query.get(job_id)
        if not vocal_master:
            return jsonify({'error': 'Job not found'}), 404
        
        # Update template and EQ settings
        vocal_master.template = template
        vocal_master.eq_settings = eq_settings
        vocal_master.status = 'processing'
        db.session.commit()
        
        # Apply fast mastering processing
        from audio_processor import apply_vocal_mastering
        
        original_path = os.path.join(app.config['UPLOAD_FOLDER'], vocal_master.original_file)
        mastered_filename = f"realtime_{vocal_master.original_file}"
        mastered_path = os.path.join(app.config['UPLOAD_FOLDER'], mastered_filename)
        
        # Apply template-specific audio processing with real-time optimization
        template_settings = {
            'template': template,
            'eq_settings': eq_settings
        }
        
        success = apply_vocal_mastering(original_path, mastered_path, template_settings)
        if not success:
            return jsonify({'error': 'Real-time processing failed'}), 500
        
        # Update record
        vocal_master.status = 'completed'
        vocal_master.mastered_file = mastered_filename
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Real-time EQ applied successfully',
            'mastered_audio_url': f'/audio/{vocal_master.id}/mastered',
            'template': template
        })
        
    except Exception as e:
        app.logger.error(f"Error applying real-time EQ: {str(e)}")
        return jsonify({'error': 'Failed to apply real-time effects'}), 500

@app.route('/api/enable-mastered/<int:job_id>')
def enable_mastered_audio(job_id):
    """Direct endpoint to enable mastered audio for a completed job"""
    vocal_master = VocalMaster.query.get(job_id)
    if not vocal_master:
        return jsonify({'error': 'Job not found'}), 404
        
    if vocal_master.status == 'completed':
        return jsonify({
            'success': True,
            'original_url': f'/audio/{job_id}/original',
            'mastered_url': f'/audio/{job_id}/mastered',
            'track_title': vocal_master.track_title,
            'status': vocal_master.status
        })
    else:
        return jsonify({
            'success': False,
            'error': f'Job status is {vocal_master.status}, not completed'
        })

@app.route('/audio/<int:job_id>/<audio_type>')
def serve_audio(job_id, audio_type):
    """Serve original or mastered audio files"""
    vocal_master = VocalMaster.query.get(job_id)
    if not vocal_master:
        return "Audio file not found", 404
    
    if audio_type == 'original':
        filename = vocal_master.original_file
    elif audio_type == 'mastered':
        if not vocal_master.mastered_file:
            return "Mastered file not ready", 404
        filename = vocal_master.mastered_file
    else:
        return "Invalid audio type", 400
    
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(file_path):
        return "File not found", 404
    
    from flask import send_file
    return send_file(file_path)

@app.route('/download/<int:job_id>')
def download_file(job_id):
    vocal_master = VocalMaster.query.get(job_id)
    if not vocal_master or vocal_master.status != 'completed':
        flash('File not ready for download')
        return redirect(url_for('vocal_mastering'))

    # In a real implementation, this would serve the actual mastered file
    flash('Download started! (This is a demo - actual file processing would occur here)')
    return redirect(url_for('vocal_mastering'))

@app.route('/test_frontend.html')
def test_frontend():
    from flask import send_from_directory
    return send_from_directory('.', 'test_frontend.html')

@app.route('/test_cover_display.html')
def test_cover_display():
    from flask import send_from_directory
    return send_from_directory('.', 'test_cover_display.html')

@app.route('/test_user_experience.html')
def test_ux_page():
    from flask import send_from_directory
    return send_from_directory('.', 'test_user_experience.html')

@app.route('/api/tokens')
def get_tokens():
    if current_user.is_authenticated:
        tokens = current_user.tokens
    else:
        tokens = session.get('tokens', 2)
    return jsonify({'tokens': tokens})

@app.route('/api/generate-video-prompt', methods=['POST'])
def generate_video_prompt():
    """Generate AI-powered scene prompts for video generation"""
    try:
        data = request.get_json()
        track_title = data.get('track_title', '').strip()
        visual_style = data.get('visual_style', '')
        user_input = data.get('user_input', '').strip()
        
        # Create contextual prompt based on inputs
        base_prompts = {
            'cyberpunk': [
                f"Neon-lit cityscape with {track_title} energy, holographic displays, rain-soaked streets",
                f"Futuristic metropolis with purple and blue neon lights, flying cars, digital billboards",
                f"Dark cyberpunk alley with glowing graffiti, steam rising, electric atmosphere",
                f"High-tech laboratory with floating holograms, laser beams, synthwave aesthetics"
            ],
            'cinematic': [
                f"Epic movie scene inspired by {track_title}, dramatic lighting, wide cinematography",
                f"Golden hour landscape with sweeping camera movements, atmospheric depth",
                f"Moody film noir setting with shadows and light, vintage aesthetic",
                f"Grand orchestral hall with spotlights, audience silhouettes, dramatic staging"
            ],
            'abstract': [
                f"Flowing abstract patterns synchronized to {track_title} rhythm, vibrant colors",
                f"Geometric shapes morphing and dancing, gradient backgrounds, particle effects",
                f"Liquid metal formations with rainbow reflections, smooth transitions",
                f"Kaleidoscopic patterns with pulsing energy, fractal designs, color explosions"
            ],
            'anime': [
                f"Anime-style scene with {track_title} theme, cherry blossoms, dramatic sky",
                f"Japanese street scene with anime characters, neon signs, evening atmosphere",
                f"Magical girl transformation sequence with sparkles and energy beams",
                f"Studio Ghibli-inspired landscape with floating islands and mystical creatures"
            ],
            'fantasy': [
                f"Enchanted forest with {track_title} magic, glowing creatures, mystical atmosphere",
                f"Medieval castle on floating island, dragons soaring, golden light rays",
                f"Wizard's tower with spell effects, magical runes, swirling energy portals",
                f"Fairy realm with luminescent plants, crystal formations, ethereal beings"
            ],
            'urban': [
                f"Street art mural coming to life with {track_title} energy, graffiti animation",
                f"Urban rooftop with city skyline, street lights, hip-hop culture vibes",
                f"Subway tunnel with colorful tags, breakdancers, underground scene",
                f"Brooklyn bridge at sunset with street performers, urban lifestyle"
            ]
        }
        
        # Get style-specific prompts
        style_prompts = base_prompts.get(visual_style, base_prompts['abstract'])
        
        # If user provided input, enhance the first prompt
        if user_input:
            enhanced_prompt = f"{style_prompts[0]} incorporating {user_input}, professional video quality"
            suggestions = style_prompts[1:4]
        else:
            enhanced_prompt = style_prompts[0] + ", professional video quality, smooth motion"
            suggestions = style_prompts[1:4]
        
        return jsonify({
            'success': True,
            'generated_prompt': enhanced_prompt,
            'suggestions': suggestions,
            'style': visual_style
        })
        
    except Exception as e:
        app.logger.error(f"Error generating prompt: {str(e)}")
        return jsonify({'error': 'Failed to generate prompt'}), 500

@app.route('/api/check-video-status/<int:job_id>')
def check_video_status(job_id):
    """Check and update video generation status"""
    try:
        video_gen = VideoGeneration.query.get(job_id)
        if not video_gen:
            return jsonify({'error': 'Video job not found'}), 404
        
        if video_gen.status == 'completed':
            # Handle video file path properly
            if video_gen.video_file:
                if video_gen.video_file.startswith('/static/'):
                    video_url = video_gen.video_file  # Already a full path
                    video_path = video_gen.video_file[1:]  # Remove leading slash for file system
                else:
                    video_url = f'/static/videos/generated/{video_gen.video_file}'  # Just filename
                    video_path = os.path.join('static/videos/generated', video_gen.video_file)
            else:
                video_url = None
                video_path = None
                
            file_size = 0
            if video_path and os.path.exists(video_path):
                file_size = os.path.getsize(video_path)
            
            return jsonify({
                'status': 'completed',
                'video_url': video_url,
                'preview_url': video_url,
                'file_size': file_size
            })
        
        # Check if video file exists locally but status is still processing
        if video_gen.video_file and video_gen.status == 'processing':
            # Check for local video files first
            video_path = f"static/videos/generated/{video_gen.video_file}"
            if os.path.exists(video_path):
                # Update status to completed if file exists
                video_gen.status = 'completed'
                db.session.commit()
                app.logger.info(f"Updated job {job_id} status to completed - found local file")
                
                file_size = os.path.getsize(video_path)
                return jsonify({
                    'status': 'completed',
                    'video_url': f'/static/videos/generated/{video_gen.video_file}',
                    'file_size': file_size,
                    'duration': video_gen.duration or '15s'
                })
        
        # Check if this is a Replicate prediction
        prediction_id = video_gen.video_file if video_gen.video_file and not video_gen.video_file.endswith('.mp4') else None
        if prediction_id and video_gen.status == 'processing':
            REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_KEY")
            # Clean up the API key in case it has export syntax
            if REPLICATE_API_TOKEN and REPLICATE_API_TOKEN.startswith("export"):
                REPLICATE_API_TOKEN = REPLICATE_API_TOKEN.split("=")[-1].strip('"\'').strip()
            if REPLICATE_API_TOKEN:
                import requests
                response = requests.get(
                    f"https://api.replicate.com/v1/predictions/{prediction_id}",
                    headers={"Authorization": f"Token {REPLICATE_API_TOKEN}"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status")
                    
                    if status == "succeeded":
                        output = data.get("output")
                        if output:
                            video_url = output[0] if isinstance(output, list) else output
                            video_gen.status = 'completed'
                            video_gen.video_file = video_url
                            db.session.commit()
                            
                            return jsonify({
                                'status': 'completed',
                                'video_url': video_url,
                                'preview_url': video_url
                            })
                    elif status == "failed":
                        video_gen.status = 'failed'
                        db.session.commit()
                        return jsonify({'status': 'failed', 'error': 'Video generation failed'})
        
        return jsonify({'status': video_gen.status})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload-video-audio', methods=['POST'])
def upload_video_audio():
    try:
        if 'audio_file' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400

        file = request.files['audio_file']
        track_title = request.form.get('track_title', '').strip()
        visual_style = request.form.get('visual_style', 'Cinematic')
        scene_prompt = request.form.get('scene_prompt', '').strip()
        duration = request.form.get('duration', '30s')
        resolution = request.form.get('resolution', '1080p')

        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        if not track_title:
            return jsonify({'error': 'Track title is required'}), 400

        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file format. Supported formats: MP3, WAV, FLAC, M4A, AAC'}), 400

        # Check token balance - Premium AI video generation with profit margin
        if current_user.is_authenticated:
            current_tokens = current_user.tokens
        else:
            current_tokens = session.get('tokens', 2)
            
        video_cost = 5  # Reduced cost for affordable video models (Zeroscope/Stable Video)
        if current_tokens < video_cost:
            return jsonify({'error': f'Insufficient tokens. Affordable AI video generation requires {video_cost} tokens.'}), 402

        # Save uploaded file
        if not file.filename:
            return jsonify({'error': 'Invalid file'}), 400
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)

        # Create video generation record
        video_gen = VideoGeneration()
        video_gen.track_title = track_title
        video_gen.audio_file = unique_filename
        video_gen.visual_style = visual_style
        video_gen.scene_prompt = scene_prompt
        video_gen.duration = duration
        video_gen.resolution = resolution
        video_gen.status = 'processing'

        db.session.add(video_gen)
        db.session.commit()

        # Deduct tokens for premium AI video generation
        if current_user.is_authenticated:
            current_user.tokens = current_tokens - video_cost
            db.session.commit()
            tokens_remaining = current_user.tokens
        else:
            session['tokens'] = current_tokens - video_cost
            tokens_remaining = session['tokens']

        # Convert duration to seconds
        duration_map = {'15s': 15, '30s': 30, '1min': 60}
        duration_seconds = duration_map.get(duration, 15)

        try:
            # CRITICAL FIX: Generate video with uploaded audio file
            video_filename = create_demo_video_with_audio(
                track_title=track_title,
                visual_style=visual_style,
                duration_seconds=duration_seconds,
                audio_file=file_path  # Use the uploaded audio file!
            )
            
            # Update database with completed video
            video_gen.status = 'completed'
            video_gen.video_file = video_filename
            db.session.commit()
            
            video_url = f'/static/videos/generated/{video_filename}'
            video_path = f"static/videos/generated/{video_filename}"
            file_size = os.path.getsize(video_path) if os.path.exists(video_path) else 0
            
            return jsonify({
                'success': True,
                'status': 'completed',
                'job_id': video_gen.id,
                'video_url': video_url,
                'preview_url': video_url,
                'duration': duration_seconds,
                'file_size': file_size,
                'tokens_remaining': tokens_remaining,
                'message': 'Video generated successfully with your audio!'
            })
            
        except Exception as e:
            # Mark video generation as failed
            video_gen.status = 'failed'
            db.session.commit()
            app.logger.error(f"Video generation failed: {str(e)}")
            
            return jsonify({
                'success': False,
                'job_id': video_gen.id,
                'error': f'Video generation failed: {str(e)}',
                'tokens_remaining': tokens_remaining
            }), 500

    except Exception as e:
        app.logger.error(f"Error uploading video audio: {str(e)}")
        return jsonify({'error': 'Failed to upload audio file'}), 500

@app.route('/api/start-video-generation', methods=['POST'])
def start_video_generation():
    try:
        data = request.get_json()
        
        # Direct video generation with validation
        visual_style = data.get('visual_style', '').strip()
        scene_prompt = data.get('scene_prompt', '').strip()
        duration = data.get('duration', '').strip()
        resolution = data.get('resolution', '').strip()
        
        # Validate required fields
        if not visual_style:
            return jsonify({'error': 'Visual style is required'}), 400
        if not duration:
            return jsonify({'error': 'Duration is required'}), 400
        if not resolution:
            return jsonify({'error': 'Resolution is required'}), 400
            
        # Set defaults if empty after validation
        if not scene_prompt:
            scene_prompt = 'music video'
        
        # Check token balance - Premium AI video generation with profit margin
        if current_user.is_authenticated:
            current_tokens = current_user.tokens
        else:
            current_tokens = session.get('tokens', 2)
            
        video_cost = 5  # Reduced cost for affordable video models (Zeroscope/Stable Video)
        if current_tokens < video_cost:
            return jsonify({'error': f'Insufficient tokens. Affordable AI video generation requires {video_cost} tokens.'}), 402
        
        # Create video generation record
        video_gen = VideoGeneration()
        video_gen.track_title = f"Generated Video {int(time.time())}"
        video_gen.audio_file = "direct_generation"  # Required field for direct generation
        video_gen.visual_style = visual_style
        video_gen.scene_prompt = scene_prompt
        video_gen.duration = duration
        video_gen.resolution = resolution
        video_gen.status = 'processing'
        
        db.session.add(video_gen)
        db.session.commit()
        
        job_id = video_gen.id
        
        # Deduct tokens for premium AI video generation
        if current_user.is_authenticated:
            current_user.tokens = current_tokens - video_cost
            db.session.commit()
        else:
            session['tokens'] = current_tokens - video_cost

        # Update status to processing
        video_gen.status = 'processing'
        db.session.commit()

        # Create enhanced prompt for video generation
        enhanced_prompt = f"{video_gen.scene_prompt or ''} {video_gen.visual_style} style, high quality, cinematic, dynamic movement"
        
        # Convert duration to seconds
        duration_map = {'15s': 15, '30s': 30, '1min': 60}
        duration_seconds = duration_map.get(video_gen.duration, 15)
        
        # Convert resolution to aspect ratio
        aspect_ratio = "16:9" if video_gen.resolution in ['720p', '1080p'] else "1:1"
        
        # Generate video using Runway ML
        result = generate_video_with_runway(
            prompt=enhanced_prompt,
            duration=min(duration_seconds, 10),  # Runway max is 10 seconds
            aspect_ratio=aspect_ratio,
            model=visual_style
        )
        
        if result.get('status') == 'processing':
            # Store prediction ID for status checking
            video_gen.video_file = result.get('prediction_id')  # Store prediction ID temporarily
            db.session.commit()
            
            # Real AI video generation in progress
            return jsonify({
                'success': True,
                'status': 'processing',
                'job_id': job_id,
                'task_id': result.get('task_id'),
                'prediction_id': result.get('prediction_id'),
                'message': result.get('message'),
                'duration': result.get('duration', duration_seconds),
                'video_url': None,
                'file_size': 0
            })
        elif result.get('status') == 'completed':
            # Video completed quickly
            video_gen.status = 'completed'
            video_gen.video_file = result.get('video_url')
            db.session.commit()
            
            return jsonify({
                'success': True,
                'status': 'completed',
                'job_id': job_id,
                'video_url': result.get('video_url'),
                'preview_url': result.get('preview_url'),
                'duration': result.get('duration', duration_seconds),
                'file_size': result.get('file_size', 0)
            })
        elif result.get('success', False):
            # Mark as completed with preview URL
            video_gen.status = 'completed'
            video_gen.video_file = result.get('preview_url', f'preview_video_{result["task_id"]}.mp4')
            db.session.commit()

            return jsonify({
                'success': True,
                'status': 'completed',
                'video_url': result['preview_url'],  # Preview video for immediate viewing
                'download_url': result['download_url'],  # Download link for full video
                'task_id': result['task_id'],
                'file_size': result.get('file_size', 0),
                'duration': result.get('duration', '15s')
            })
        else:
            # Mark as failed
            video_gen.status = 'failed'
            db.session.commit()
            
            return jsonify({
                'success': False,
                'error': result.get('error', 'Video generation failed')
            }), 500

    except Exception as e:
        # Mark as failed in database if job_id exists
        video_gen = None
        try:
            if 'job_id' in locals():
                video_gen = VideoGeneration.query.get(job_id)
                if video_gen:
                    video_gen.status = 'failed'
                    db.session.commit()
        except:
            pass  # Ignore if database update fails
        
        app.logger.error(f"Error starting video generation: {str(e)}")
        return jsonify({'error': f'Failed to generate video: {str(e)}'}), 500

@app.route('/api/video-job-status/<int:job_id>')
def video_job_status(job_id):
    video_gen = VideoGeneration.query.get(job_id)
    if not video_gen:
        return jsonify({'error': 'Job not found'}), 404

    response = {
        'status': video_gen.status,
        'track_title': video_gen.track_title,
        'visual_style': video_gen.visual_style,
        'created_at': video_gen.created_at.isoformat()
    }
    
    # Add video URL if completed
    if video_gen.status == 'completed' and video_gen.video_file:
        response['video_url'] = f'/static/videos/generated/{video_gen.video_file}'
        
        # Check file size
        import os
        video_path = os.path.join('static/videos/generated', video_gen.video_file)
        if os.path.exists(video_path):
            response['file_size'] = os.path.getsize(video_path)
        
    return jsonify(response)

@app.route('/api/video-status/<int:job_id>')
def video_status(job_id):
    """Alias for video job status"""
    return video_job_status(job_id)

@app.route('/download-video/<task_id>')
def download_video_by_task(task_id):
    """Download full-quality video by task ID (like real AI platforms)"""
    try:
        # Real platforms check payment/credits here
        video_filename = f"preview_video_{task_id}.mp4"
        video_path = f"static/videos/generated/{video_filename}"
        
        if os.path.exists(video_path):
            return send_file(video_path, as_attachment=True, 
                           download_name=f"ai_video_{task_id}.mp4",
                           mimetype='video/mp4')
        else:
            return jsonify({'error': 'Video file not found'}), 404
            
    except Exception as e:
        return jsonify({'error': f'Download failed: {str(e)}'}), 500

@app.route('/download-video/<int:job_id>')
def download_video(job_id):
    """Download video by database job ID"""
    try:
        video_gen = VideoGeneration.query.get(job_id)
        if not video_gen or video_gen.status != 'completed':
            flash('Video not ready for download')
            return redirect(url_for('video_generator'))

        # Handle both old absolute paths and new relative filenames
        if video_gen.video_file.startswith('/'):
            video_path = video_gen.video_file  # Old absolute path
        else:
            video_path = os.path.join('static', 'videos', 'generated', video_gen.video_file)
        
        if not os.path.exists(video_path):
            flash('Video file not found')
            return redirect(url_for('video_generator'))
        

        return send_file(
            video_path,
            as_attachment=True,
            download_name=f"{video_gen.track_title}_generated_video.mp4",
            mimetype='video/mp4'
        )
        
    except Exception as e:
        app.logger.error(f"Error downloading video: {str(e)}")
        flash('Error downloading video')
        return redirect(url_for('video_generator'))

# Placeholder functions for different AI models
def create_professional_fallback_cover(artist_name, album_title, genre):
    """Create high-quality fallback cover art"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import uuid
        import os
        
        # Professional color schemes
        color_schemes = {
            'Hip Hop': {'bg': (20, 20, 20), 'accent': (255, 215, 0), 'text': (255, 255, 255)},
            'Pop': {'bg': (255, 182, 193), 'accent': (255, 20, 147), 'text': (255, 255, 255)},
            'Rock': {'bg': (139, 0, 0), 'accent': (255, 69, 0), 'text': (255, 255, 255)},
            'Electronic': {'bg': (0, 191, 255), 'accent': (0, 255, 255), 'text': (255, 255, 255)},
            'R&B': {'bg': (75, 0, 130), 'accent': (255, 215, 0), 'text': (255, 255, 255)},
            'Jazz': {'bg': (184, 134, 11), 'accent': (255, 215, 0), 'text': (255, 255, 255)},
            'Indie': {'bg': (70, 130, 180), 'accent': (255, 182, 193), 'text': (255, 255, 255)}
        }
        
        scheme = color_schemes.get(genre, color_schemes['Pop'])
        
        # Create high-quality image
        img = Image.new('RGB', (1024, 1024), color=scheme['bg'])
        draw = ImageDraw.Draw(img)
        
        # Add professional design elements
        draw.rectangle([60, 60, 964, 964], outline=scheme['accent'], width=8)
        draw.rectangle([100, 100, 924, 924], outline=scheme['text'], width=4)
        
        # Add text with better positioning
        try:
            font = ImageFont.load_default()
        except:
            font = None
        
        # Album title
        album_bbox = draw.textbbox((0, 0), album_title, font=font)
        album_width = album_bbox[2] - album_bbox[0]
        draw.text((512 - album_width//2, 450), album_title, fill=scheme['text'], font=font)
        
        # Artist name
        artist_bbox = draw.textbbox((0, 0), artist_name, font=font)
        artist_width = artist_bbox[2] - artist_bbox[0]
        draw.text((512 - artist_width//2, 520), artist_name, fill=scheme['accent'], font=font)
        
        # Genre badge
        genre_text = f"• {genre.upper()} •"
        genre_bbox = draw.textbbox((0, 0), genre_text, font=font)
        genre_width = genre_bbox[2] - genre_bbox[0]
        draw.rectangle([512 - genre_width//2 - 10, 580, 512 + genre_width//2 + 10, 610], 
                       fill=scheme['accent'])
        draw.text((512 - genre_width//2, 585), genre_text, fill=(0, 0, 0), font=font)
        
        # Save image
        filename = f"cover_{uuid.uuid4().hex[:8]}.jpg"
        filepath = f"static/images/generated/{filename}"
        os.makedirs("static/images/generated", exist_ok=True)
        img.save(filepath, 'JPEG', quality=95)
        
        return {
            'success': True,
            'image_url': f'/static/images/generated/{filename}',
            'model_used': 'Professional Cover Generator'
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def generateWithStableDiffusion(ai_prompt, artist_name, album_title):
    return create_professional_fallback_cover(artist_name, album_title, 'Electronic')

def generateWithDalle3(ai_prompt, artist_name, album_title):
    # Try OpenAI first, fallback to professional cover generator
    try:
        return generate_cover_art_image(ai_prompt, artist_name, album_title)
    except:
        return create_professional_fallback_cover(artist_name, album_title, 'Pop')

def generateWithMidjourney(ai_prompt, artist_name, album_title):
    return create_professional_fallback_cover(artist_name, album_title, 'Indie')

def generateWithDreamShaper(ai_prompt, artist_name, album_title):
    return create_professional_fallback_cover(artist_name, album_title, 'Rock')

def generateWithPlayground(ai_prompt, artist_name, album_title):
    return create_professional_fallback_cover(artist_name, album_title, 'Hip Hop')

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))
        
        if not email or not password:
            flash('Email and password are required.')
            return render_template('login.html')
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Invalid email or password.')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validation
        if not all([username, email, password, confirm_password]):
            flash('All fields are required.')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Passwords do not match.')
            return render_template('register.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters long.')
            return render_template('register.html')
        
        if len(username) < 3 or len(username) > 20:
            flash('Username must be between 3 and 20 characters.')
            return render_template('register.html')
        
        # Check if user already exists
        if User.query.filter_by(email=email).first():
            flash('Email address already registered.')
            return render_template('register.html')
        
        if User.query.filter_by(username=username).first():
            flash('Username already taken.')
            return render_template('register.html')
        
        # Create new user
        user = User()
        user.username = username
        user.email = email
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        login_user(user)
        flash('Account created successfully! Welcome to SLNP Art!', 'success')
        return redirect(url_for('index'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

# Configure Stripe
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

# Token purchase routes
@app.route('/buy-tokens')
def buy_tokens():
    return render_template('buy_tokens.html')

@app.route('/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    try:
        package = request.form.get('package')
        
        # Define token packages
        packages = {
            'starter': {
                'tokens': 100,
                'price': 999,  # $9.99 in cents
                'name': 'Starter Pack - 100 Tokens'
            },
            'pro': {
                'tokens': 300,
                'price': 2499,  # $24.99 in cents
                'name': 'Pro Pack - 300 Tokens'
            },
            'ultimate': {
                'tokens': 700,  # Adjusted for $1+ profit margin
                'price': 6999,  # $69.99 in cents
                'name': 'Ultimate Pack - 700 Tokens'
            }
        }
        
        if package not in packages:
            flash('Invalid package selected.')
            return redirect(url_for('buy_tokens'))
        
        selected_package = packages[package]
        
        # Get domain for success/cancel URLs
        YOUR_DOMAIN = request.host_url.rstrip('/')
        
        # Create Stripe checkout session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[
                {
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': selected_package['name'],
                            'description': f"Get {selected_package['tokens']} tokens for SLNP Art"
                        },
                        'unit_amount': selected_package['price'],
                    },
                    'quantity': 1,
                }
            ],
            mode='payment',
            success_url=YOUR_DOMAIN + url_for('payment_success') + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=YOUR_DOMAIN + url_for('payment_cancel'),
            metadata={
                'user_id': current_user.id,
                'package': package,
                'tokens': selected_package['tokens']
            }
        )
        
        if checkout_session and checkout_session.url:
            return redirect(checkout_session.url, code=303)
        else:
            flash('Error creating payment session. Please try again.')
            return redirect(url_for('buy_tokens'))
        
    except Exception as e:
        app.logger.error(f"Error creating checkout session: {str(e)}")
        flash('Error creating payment session. Please try again.')
        return redirect(url_for('buy_tokens'))

@app.route('/payment-success')
@login_required
def payment_success():
    session_id = request.args.get('session_id')
    
    if session_id:
        try:
            # Retrieve the checkout session
            checkout_session = stripe.checkout.Session.retrieve(session_id)
            
            if checkout_session.payment_status == 'paid':
                # Add tokens to user account
                tokens_to_add = int(checkout_session.metadata.get('tokens', 0) if checkout_session.metadata else 0)
                current_user.tokens += tokens_to_add
                db.session.commit()
                
                flash(f'Successfully purchased {tokens_to_add} tokens!', 'success')
        except Exception as e:
            app.logger.error(f"Error processing payment success: {str(e)}")
            flash('Payment completed but there was an error updating your account. Please contact support.', 'warning')
    
    return render_template('payment_success.html')

@app.route('/payment-cancel')
def payment_cancel():
    return render_template('payment_cancel.html')

# Video download route
@app.route('/download-video-file/<task_id>')
def download_video_file(task_id):
    try:
        # Find the video file based on task_id or latest video
        video_files = os.listdir('static/videos/generated/')
        video_files.sort(key=lambda x: os.path.getctime(f'static/videos/generated/{x}'), reverse=True)
        
        if video_files:
            latest_video = video_files[0]
            video_path = f'static/videos/generated/{latest_video}'
            return send_file(video_path, as_attachment=True, download_name=f'generated_video_{task_id}.mp4')
        else:
            flash('Video file not found.')
            return redirect(url_for('video_generator'))
            
    except Exception as e:
        app.logger.error(f"Error downloading video: {str(e)}")
        flash('Error downloading video file.')
        return redirect(url_for('video_generator'))

# Initialize session tokens for demo (anonymous users)
@app.before_request
def before_request():
    if not current_user.is_authenticated and 'tokens' not in session:
        session['tokens'] = 64
