# **Gammu SMS Web Manager**

A simple yet powerful Flask web application for managing SMS messages stored by [Gammu](https://wammu.eu/gammu/) in a MySQL database. This tool provides a modern, real-time web interface to view, manage, and receive notifications for incoming SMS.

## **Features**

* **Modern UI:** A clean, responsive user interface built with Tailwind CSS.  
* **Real-Time Notifications:** Get instant browser notifications when a new SMS arrives.  
* **Live UI Updates:** The message list updates automatically, without needing a page refresh.  
* **Bulk Actions:** Select multiple messages to mark as read or delete them all at once.  
* **Easy Setup:** Single-file application with minimal dependencies.  
* **Custom Modals:** A polished user experience with custom confirmation dialogs instead of native browser alerts.

## **Prerequisites**

* Python 3.13.1+
* A GSM modem or mobile phone that can be connected to your server. (I used [GPRS SIM800 Module](https://de.aliexpress.com/item/4000890352364.html?spm=a2g0o.order_list.order_list_main.5.53971802mb0CD6&gatewayAdapt=glo2deu))
* A MySQL server.  
* Poetry For dependency management.
* [asdf](https://asdf-vm.com/) (optional)

## **Part 1: Gammu Installation and Configuration**

Before setting up the web app, you need to install and configure Gammu (smsdrc) to store SMS messages in your MySQL database.

### **1\. Install Gammu and SMSD**

On Debian-based Linux distributions (like Ubuntu or Raspberry Pi OS), you can install Gammu and the Gammu SMS Daemon (SMSD) using the package manager.

```bash
  sudo apt-get update  
  sudo apt-get install gammu gammu-smsd
```

### **2\. Configure gammu-smsd to Connect to Your Modem**

First, you need to configure Gammu to recognize your modem.

* Connect your modem to the server. It will usually be available at a path like `/dev/ttyUSB0` or `/dev/ttyACM0`.  
* Create `/etc/gammu-smsdrc` file like below:

```bash
  sudo nano /etc/gammu-smsdrc
```

This is an example of `gammu-smsdrc` config:

```bash

[gammu]
device = /dev/ttyUSB0
connection = at115200

[smsd]
service = mysql
driver = native_mysql
host = localhost
user = gammu_user
password = "<password>"
database = gammu_db
logfile = /var/log/gammu-smsd.log
loglevel = debug

```

### **3\. Set Up the MySQL Database**

The Gammu SMSD service needs a database to store messages.

* Log in to your MySQL server and create a new database and user for Gammu.  

```sql
  CREATE DATABASE gammu\_db;  
  CREATE USER 'gammu\_user'@'localhost' IDENTIFIED BY 'your\_secret\_password';  
  GRANT ALL PRIVILEGES ON gammu\_db.\* TO 'gammu\_user'@'localhost';  
  FLUSH PRIVILEGES;  
  EXIT;
```

* Gammu comes with a SQL script to create the necessary tables. Find and import it into your new database. The path may vary, but it's often found here:  
  \# The path to mysql.sql might be different on your system.  
  
  ```bash
    mysql \-u gammu\_user \-p gammu\_db \< /usr/share/doc/gammu/examples/sql/mysql.sql
  ````

## **Part 2: Web App Setup and Installation**

Now that Gammu is configured, you can set up the web application to manage the messages.

### **1\. Clone the Repository**

```bash
git clone <your-repository-url>  
cd <your-repository-directory>
```

### **2\. Install Dependencies**

Use Poetry to install the required Python packages from the pyproject.toml file.  
`poetry install`

### **3\. Configure Environment Variables**

Create a .env file to hold your database credentials. **These must match the credentials you used for Gammu SMSD.**  
\# You can create this from scratch or copy an example if one exists  
nano .env

Add the following content to the .env file:  

```bash
# .env file  
DB_HOST=localhost  
DB_USER=gammu_user  
DB_PASSWORD='your_secret_password'  
DB_NAME=gammu_db  
SECRET_KEY='A long random string for flask sessions'
```

**Important:** The SECRET\_KEY is used by Flask to secure user sessions. For generating a long, random string use this command `python -c "import secrets; print(secrets.token_hex(32))"`

### **4\. Running the Application**

#### Development Mode

Once the setup is complete, you can run the Flask application:  
`poetry run python app.py`
You will see output in your terminal indicating that the server is running:  
Starting Flask server...  
Access the app at <http://127.0.0.1:5000>

Open your web browser and navigate to **<http://127.0.0.1:5000>** to start using the SMS manager.

#### Production Mode

For production deployments, it is recommended to use a production-ready WSGI server like [Gunicorn](https://gunicorn.org/).

First, install Gunicorn (if not already installed):

```bash
poetry add gunicorn
```

Then, run the application with Gunicorn:

```bash
poetry run gunicorn app:app
```

You can adjust the number of worker processes and bind to a specific address/port as needed:

```bash
poetry run gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

For best results, consider running Gunicorn behind a reverse proxy such as Nginx for improved security and performance.

##### **Running with systemd and Gunicorn**

To run the web application as a background service, you can create a `systemd` unit file for Gunicorn.

1. **Create a systemd service file** (replace `<your-user>` and `<your-repository-directory>` as needed):

   ```bash
   sudo nano /etc/systemd/system/gammu-sms-web.service
   ```

2. **Add the following content:**

   ```ini
   [Unit]
   Description=Gammu SMS Web Manager (Gunicorn)
   After=network.target

   [Service]
   User=<your-user>
   Group=www-data
   WorkingDirectory=/home/<your-user>/<your-repository-directory>
   Restart=on-failure
   Environment=POETRY_VIRTUALENVS_IN_PROJECT=true
   ExecStart=/usr/bin/poetry run uunicorn -w 4 -b 0.0.0.0:5000 app:app

   [Install]
   WantedBy=multi-user.target
   ```

3. **Reload systemd and start the service:**

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl start gammu-sms-web
   sudo systemctl enable gammu-sms-web
   ```

4. **Check the status:**

```bash
sudo systemctl status gammu-sms-web
```

Your Flask app will now run as a service and restart automatically if it crashes or the server reboots.

## **License**

This project is open-source and available under the [MIT License](https://www.google.com/search?q=LICENSE).

<!-- 
TODOs: 
- clean up the readme
- clean up the code 
- long term test

-->