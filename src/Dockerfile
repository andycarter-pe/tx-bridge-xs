# Use the official Python image as the base image
FROM python:3.8-slim

# Set the working directory in the container
WORKDIR /app

# Install pandas using pip
RUN pip install flask plotly pytz numpy scipy pandas boto3

# Copy the rest of your application code into the Docker image
COPY . /app

# Expose port 5000 if needed
EXPOSE 5000

# Specify the command to run your application
CMD ["python", "app.py"]