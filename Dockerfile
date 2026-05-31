# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Install system dependencies, including OpenJDK Java Runtime (required for Apktool)
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-17-jre-headless \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application files into the container
COPY . .

# Set environment variables
ENV PORT=5050
ENV PYTHONUNBUFFERED=1

# Expose the port the app runs on
EXPOSE 5050

# Run server.py when the container launches
CMD ["python", "server.py"]
