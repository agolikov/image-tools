# Use the official Python image as the base image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY src/requirements.txt requirements.txt

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application source files into the container
COPY src/ .

# Expose the port the app runs on
EXPOSE 5050

# Command to run the application
CMD ["python", "app.py"]