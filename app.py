from flask import Flask, render_template, request, jsonify, url_for, send_from_directory
from runwayml import RunwayML
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from PIL import Image
import os
import time
import logging
import uuid

load_dotenv()

app = Flask(__name__)
client = RunwayML()

# Configuration
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'  # Use /tmp for Vercel
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB limit

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Set up logging
logging.basicConfig(level=logging.INFO)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def get_aspect_ratio(image_path):
    with Image.open(image_path) as img:
        width, height = img.size
    aspect_ratio = width / height
    return "16:9" if aspect_ratio > 1 else "9:16"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/generate', methods=['POST'])
def generate_video():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file part'})
    
    file = request.files['file']
    prompt_text = request.form.get('promptText', '')
    
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No selected file'})
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4()}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)
        
        aspect_ratio = get_aspect_ratio(file_path)
        
        # Use the application's URL for the image
        image_url = url_for('uploaded_file', filename=unique_filename, _external=True)
        
        try:
            task = client.image_to_video.create(
                model='gen3a_turbo',
                prompt_image=image_url,
                prompt_text=prompt_text,
                ratio=aspect_ratio,
                duration=5
            )

            task_id = task.id

            # Poll the task until it's complete
            while True:
                task_status = client.tasks.retrieve(task_id)
                logging.info(f"Task status: {task_status}")
                
                if task_status.status in ['SUCCEEDED', 'FAILED']:
                    break
                time.sleep(10)

            if task_status.status == 'SUCCEEDED':
                task_info = {
                    'status': task_status.status,
                    'id': task_status.id,
                    'created_at': str(task_status.created_at),
                    'output': task_status.output if hasattr(task_status, 'output') else None
                }
                
                logging.info(f"Extracted task info: {task_info}")
                
                return jsonify({
                    'status': 'success', 
                    'task_info': task_info
                })
            else:
                return jsonify({'status': 'error', 'message': 'Video generation failed'})

        except Exception as e:
            logging.error(f"Error occurred: {str(e)}")
            return jsonify({'status': 'error', 'message': str(e)})
        finally:
            # Clean up the uploaded file
            os.remove(file_path)
    
    return jsonify({'status': 'error', 'message': 'Invalid file type'})

# This is for local development
if __name__ == '__main__':
    app.run(debug=True)