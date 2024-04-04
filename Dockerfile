# Use the official Python image as the base image
FROM python:3.8-slim

# Set the working directory in the container
WORKDIR /app

# Install dependencies using pip
RUN pip install flask plotly pytz numpy scipy pandas boto3

# Set environment variable
ENV PATH_TO_BRIDGE_JSONS="s3://tx-bridge-xs-json/"

# Create a user named 'kisters' to run your application instead of using root
RUN useradd -m kisters

# Copy the rest of your application code into the Docker image
COPY . /app

# Change the ownership of the /app directory to 'kisters'
RUN chown -R kisters:kisters /app

# Switch to your new user 'kisters'
USER kisters

# Expose port 5000 if needed
EXPOSE 5000

# Specify the command to run your application
CMD ["python", "app.py"]
