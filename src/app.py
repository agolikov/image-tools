from flask import Flask, request, jsonify, redirect, render_template, send_file, url_for, send_from_directory
from PIL import Image
from flasgger import Swagger
import os
import zipfile
import io
from werkzeug.utils import secure_filename

app = Flask(__name__, static_folder="static")
swagger = Swagger(app, template_file='swagger.yaml')

# Configuration
UPLOAD_FOLDER = "static/uploads"
OUTPUT_FOLDER = "static/output"
THUMBNAIL_FOLDER = "static/thumbnails"
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
PRESET_SIZES = [
    (16, 16),
    (32, 32),
    (48, 48),
    (64, 64),
    (128, 128),
    (512, 512)
]

# Ensure folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(THUMBNAIL_FOLDER, exist_ok=True)

uploaded_image_name = None


def allowed_file(filename):
    """
    Check if the uploaded file has a valid image extension.
    """
    if '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS:
        return True
    return False


def is_image(file_path):
    """
    Try opening the file with PIL to check if it's a valid image.
    """
    try:
        with Image.open(file_path) as img:
            img.verify()  # This will raise an exception if the file is not a valid image
        return True
    except (IOError, SyntaxError):
        return False

def get_unique_filename(upload_folder, filename):
    """
    Check if the file already exists in the upload folder and add a counter to the filename if necessary.
    """
    # Split the file name into name and extension
    name, extension = os.path.splitext(filename)

    # Generate the full path of the file
    full_path = os.path.join(upload_folder, filename)

    # Check if the file already exists and add a counter to the filename
    counter = 1
    while os.path.exists(full_path):
        # Generate a new filename with a counter
        filename = f"{name}_{counter}{extension}"
        full_path = os.path.join(upload_folder, filename)
        counter += 1

    return filename

@app.route('/')
def index():
    """
    Render the homepage with the form to upload an image.
    """
    global uploaded_image_name
    # Get list of processed zip files for the history
    history_files = [f for f in os.listdir(OUTPUT_FOLDER) if f.endswith('.zip')]
    history_entries = []

    for zip_file in history_files:
        zip_name = zip_file
        thumbnail_name = f"thumbnail_{zip_file}.png"
        history_entries.append({
            'zip_file': zip_name,
            'thumbnail_url': 'thumbnails/' + thumbnail_name
        })

    return render_template(
        "index.html",
        preset_sizes=PRESET_SIZES,
        history_entries=history_entries,
        uploaded_image=uploaded_image_name
    )


@app.route('/upload', methods=['POST'])
def upload_image():
    """
    Upload an image, store it, and preview it on the page.
    """
    global uploaded_image_name

    if 'image' not in request.files:
        return redirect(url_for('index'))

    image_file = request.files['image']
    if image_file.filename == '':
        return redirect(url_for('index'))

    if not allowed_file(image_file.filename):
        return jsonify({"error": "Invalid file format. Only image files are allowed."}), 400

    # Get the unique filename
    unique_filename = get_unique_filename(UPLOAD_FOLDER, image_file.filename)

    filename = secure_filename(unique_filename)
    uploaded_image_name = filename  # Store for preview

    file_path = os.path.join(UPLOAD_FOLDER, filename)

    # Save the file
    image_file.save(file_path)

    if not is_image(file_path):
        os.remove(file_path)  # Delete the invalid image file
        return jsonify({"error": "Uploaded file is not a valid image."}), 400

    return redirect(url_for('index'))


@app.route('/convert', methods=['POST'])
def convert_image():
    """
    Convert the uploaded image into multiple preset sizes and return a ZIP file.
    """
    global uploaded_image_name

    if not uploaded_image_name:
        return redirect(url_for('index'))

    # Get selected sizes from the form
    selected_sizes = request.form.getlist('sizes')
    sizes = [tuple(map(int, size.split(','))) for size in selected_sizes]

    # Get the desired output format
    output_format = request.form.get('format', 'png').lower()
    if output_format not in ['png', 'jpg']:
        return jsonify({"error": "Invalid format. Only 'png' and 'jpg' are allowed."}), 400

    try:
        # Process the uploaded image
        input_path = os.path.join(UPLOAD_FOLDER, uploaded_image_name)

        zip_buffer = io.BytesIO()  # Create an in-memory ZIP file
        zip_filename = f"{os.path.splitext(uploaded_image_name)[0]}_converted.zip"
        zip_filepath = os.path.join(OUTPUT_FOLDER, zip_filename)

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            with Image.open(input_path) as img:
                thumbnail_image = None  # Variable to hold the 128x128 thumbnail
                for size in sizes:
                    resized_img = img.resize(size, Image.Resampling.LANCZOS)
                    output_file_name = f"{os.path.splitext(uploaded_image_name)[0]}_{size[0]}x{size[1]}.{output_format}"
                    output_path = os.path.join(OUTPUT_FOLDER, output_file_name)

                    # Save resized image to the output folder
                    resized_img.save(output_path, format=output_format.upper())

                    # Add the image to the ZIP file
                    zip_file.write(output_path, arcname=output_file_name)

                    os.remove(output_path)

                    # If this is the 128x128 size, create the thumbnail
                    if size == (128, 128):
                        thumbnail_image = resized_img

                # Create a thumbnail of the 128x128 image for the history preview
                if thumbnail_image:
                    thumbnail_path = os.path.join(THUMBNAIL_FOLDER, f"thumbnail_{zip_filename}.png")
                    thumbnail_image.save(thumbnail_path)

        zip_buffer.seek(0)

        # Save the ZIP archive
        with open(zip_filepath, 'wb') as f:
            f.write(zip_buffer.read())

        # Clear uploaded image name after conversion
        uploaded_image_name = None

        return send_file(
            zip_filepath,
            mimetype='application/zip',
            as_attachment=True,
            download_name=zip_filename
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/delete/<filename>')
def delete_file(filename):
    """
    Delete a specific processed file (ZIP file).
    """
    zip_path = os.path.join(OUTPUT_FOLDER, filename)
    thumbnail_path = os.path.join(THUMBNAIL_FOLDER, f"thumbnail_{filename}.png")

    if os.path.exists(zip_path):
        os.remove(zip_path)
    if os.path.exists(thumbnail_path):
        os.remove(thumbnail_path)

    return redirect(url_for('index'))

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5050)