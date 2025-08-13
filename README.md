# **Gammu SMS Web Manager**

A simple yet powerful Flask web application for managing SMS messages stored by Gammu in a MySQL database. This tool provides a modern, real-time web interface to view, manage, and receive notifications for incoming SMS.

## **Features**

* **Modern UI:** A clean, responsive user interface built with Tailwind CSS.  
* **Real-Time Notifications:** Get instant browser notifications when a new SMS arrives.  
* **Live UI Updates:** The message list updates automatically without needing a page refresh.  
* **Bulk Actions:** Select multiple messages to mark as read or delete them all at once.  
* **Secure Configuration:** Keep your database credentials safe and separate from the code using environment variables.  
* **Easy Setup:** Single-file application with minimal dependencies.  
* **Custom Modals:** A polished user experience with custom confirmation dialogs instead of native browser alerts.

## **Prerequisites**

* Python 3.13.1+
* A GSM modem or mobile phone that can be connected to your server (e.g., via USB).  
* A MySQL server.  
* Poetry (for dependency management).

## **Part 1: Gammu Installation and Configuration**

Before setting up the web app, you need to install and configure Gammu to store SMS messages in your MySQL database.

### **1\. Install Gammu and SMSD**

On Debian-based Linux distributions (like Ubuntu or Raspberry Pi OS), you can install Gammu and the Gammu SMS Daemon (SMSD) using the package manager.  
sudo apt-get update  
sudo apt-get install gammu gammu-smsd

### **2\. Configure Gammu to Connect to Your Modem**

First, you need to configure Gammu to recognize your modem.

* Connect your modem/phone to the server. It will usually be available at a path like /dev/ttyUSB0 or /dev/ttyACM0.  
* Run the interactive configuration tool:  
  gammu-config

* Follow the prompts. Select the correct port and connection type for your device. This will create a configuration file at \~/.gammurc.  
* Test the connection:  
  gammu identify

  If successful, this command will display information about your modem.

### **3\. Set Up the MySQL Database**

The Gammu SMSD service needs a database to store messages.

* Log in to your MySQL server and create a new database and user for Gammu.  
  CREATE DATABASE gammu\_db;  
  CREATE USER 'gammu\_user'@'localhost' IDENTIFIED BY 'your\_secret\_password';  
  GRANT ALL PRIVILEGES ON gammu\_db.\* TO 'gammu\_user'@'localhost';  
  FLUSH PRIVILEGES;  
  EXIT;

* Gammu comes with a SQL script to create the necessary tables. Find and import it into your new database. The path may vary, but it's often found here:  
  \# The path to mysql.sql might be different on your system.  
  mysql \-u gammu\_user \-p gammu\_db \< /usr/share/doc/gammu/examples/sql/mysql.sql

### **4\. Configure Gammu SMSD**

Now, configure the SMS daemon to use your new database. This is done in the /etc/gammu-smsdrc file.

* Edit the file with root privileges:  
  sudo nano /etc/gammu-smsdrc

* Make sure the file contains the following sections and values. Pay close attention to the \[gammu\] and \[smsd\] sections.  
  \# /etc/gammu-smsdrc

  \[gammu\]  
  \# This should match the port and connection from your \~/.gammurc file  
  port \= /dev/ttyUSB0  
  connection \= at115200

  \[smsd\]  
  service \= sql  
  driver \= native\_mysql  
  logfile \= /var/log/gammu-smsd  
  debuglevel \= 1

  \# Database connection settings  
  host \= localhost  
  user \= gammu\_user  
  password \= your\_secret\_password  
  database \= gammu\_db

* Enable and start the Gammu SMSD service:  
  sudo systemctl enable gammu-smsd  
  sudo systemctl start gammu-smsd

* Check its status to ensure it's running without errors:  
  sudo systemctl status gammu-smsd

At this point, any new SMS messages received by your modem will be automatically stored in the gammu\_db database.

## **Part 2: Web App Setup and Installation**

Now that Gammu is configured, you can set up the web application to manage the messages.

### **1\. Clone the Repository**

git clone \<your-repository-url\>  
cd \<your-repository-directory\>

### **2\. Install Dependencies**

Use Poetry to install the required Python packages from the pyproject.toml file.  
poetry install

### **3\. Configure Environment Variables**

Create a .env file to hold your database credentials. **These must match the credentials you used for Gammu SMSD.**  
\# You can create this from scratch or copy an example if one exists  
nano .env

Add the following content to the .env file:  
\# .env file  
DB\_HOST=localhost  
DB\_USER=gammu\_user  
DB\_PASSWORD='your\_secret\_password'  
DB\_NAME=gammu\_db  
SECRET\_KEY='a\_long\_random\_string\_for\_flask\_sessions'

**Important:** The SECRET\_KEY is used by Flask to secure user sessions. Generate a long, random string for this value.

### **4\. Running the Application**

Once the setup is complete, you can run the Flask application:  
poetry run python gammu\_sms\_webapp.py

You will see output in your terminal indicating that the server is running:  
Starting Flask server...  
Access the app at http://127.0.0.1:5000

Open your web browser and navigate to **http://127.0.0.1:5000** to start using the SMS manager.

## **License**

This project is open-source and available under the [MIT License](https://www.google.com/search?q=LICENSE).

<!-- 
TODOs: 
- clean up the readme
- clean up the code 
- long term test

-->