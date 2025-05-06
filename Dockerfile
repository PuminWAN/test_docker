# Use the official Python image from the Docker Hub
FROM python:3.12.4

# Set the timezone environment variable
ENV TZ=Asia/Bangkok

# Set the working directory
WORKDIR /app

# Copy requirements file to the working directory
COPY requirements.txt ./

# Install tzdata package and set the time zones
RUN apt-get update && \
    apt-get install -y tzdata && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    echo $TZ > /etc/timezone && \
    apt-get clean

# Install dependencies
COPY . /app 
RUN pip install -r requirements.txt

# Command to run your application
CMD ["python", "-u", "test_docker.py"]