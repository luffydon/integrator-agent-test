# Use an official lightweight Python image as a parent image
FROM python:3.11-slim

# Set a standard working directory for the application
WORKDIR /usr/src/app

# Copy and install dependencies first to leverage Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project context into the working directory
COPY . .

# Expose the port the application will run on
EXPOSE 8080

# Define the command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]