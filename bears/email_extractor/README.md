
# Automated Processing of Images in Email attachments

> An automated system for extracting and analyzing wildlife camera images from emails using Microsoft Graph API and Tesseract OCR technology.

[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Documentation](#documentation)
- [Project Structure](#project-structure)
- [API & Modules](#api--modules)
- [CI/CD](#cicd)
- [Troubleshooting](#troubleshooting)

## Overview

This project was developed for **OTH Regensburg** to automate wildlife monitoring and analysis. The system automatically retrieves emails containing camera images, extracts metadata (timestamp, animal type, camera identifier) using OCR technology, and stores the information in a MariaDB database for later exploitation through a web interface.

### Use Cases

- Automated wildlife monitoring
- Processing camera pictures
- Metadata extraction from images
- Structured storage for analysis and visualization

## Features

### Core Functionality

- **Microsoft Graph API Authentication**: Secure OAuth 2.0 connection via MSAL
- **Email Retrieval**: Automatic access to emails and attachments
- **Advanced OCR**: Text extraction from images using EasyOCR
- **Intelligent Parsing**: Automatic recognition of timestamp and animal type
- **Database Storage**: Persistent storage in MariaDB
- **Sphinx Documentation**: Auto-generated documentation from Python docstrings

### Technology Stack

| Technology | Purpose |
|------------|---------|
| **Python 3.12+** | Primary language |
| **Microsoft Graph API** | Office 365 email access |
| **MSAL** | Microsoft authentication |
| **EasyOCR** | Optical character recognition |
| **Pillow (PIL)** | Image processing |
| **MySQL Connector** | Database interface |
| **Sphinx + Furo** | Documentation generation |
| **Poetry** | Dependency management |

## Prerequisites

### System Requirements

- **OS**: Linux (Ubuntu/Debian recommended) or Windows
- **Python**: Version 3.12 or higher
- **Tesseract OCR**: Version 4.0+
- **Database**: MariaDB 10.5+ or MySQL 8.0+

### Azure AD Access

You need an **Azure AD Tenant** configured with:
- A **registered application** in Azure AD with:
  - Microsoft Graph API permissions (`Mail.Read`, `Mail.ReadWrite`)
  - A generated client secret
  - Application-type authentication (non-delegated)

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd wildlife_pictures_extraction
```

### 2. Install Poetry (if needed)

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

### 3. Install Python Dependencies

```bash
# For production use (with OCR capabilities)
poetry install --with ocr

# For documentation only (lighter, without heavy ML dependencies)
poetry install
```

> **Note**: The OCR dependencies (EasyOCR, PyTorch) are optional and quite large (~2GB). If you only need to build documentation, use `poetry install` without the `--with ocr` flag.

## Configuration

### `.env` File

Create a `.env` file in the project root with the following variables:

```env
# Database Configuration
DB_HOST=host
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DB_NAME=wildlife_pictures

# Microsoft Graph API Configuration
TENANT_ID=your_azure_tenant_id
CLIENT_ID=your_application_client_id
CLIENT_SECRET=your_client_secret
AUTHORITY=https://login.microsoftonline.com/your_tenant_id
SCOPE=https://graph.microsoft.com/.default
GRAPH_ROOT=https://graph.microsoft.com/v1.0

MAILBOX=inbox_you_want_to_access
SENDER_MAILBOX=email_from_the_sender
```

## Usage

### Running the Main Script

```bash
poetry run python WildlifePictureExtractor.py
```

## Documentation

### Sphinx Documentation

Complete project documentation is automatically generated from Python docstrings.

#### Build Documentation Locally

```bash
cd docs
poetry run make html
```

Documentation will be available in `docs/build/html/index.html`.

#### Open Documentation

```bash
# Linux
xdg-open docs/build/html/index.html

# Windows
start docs/build/html/index.html
```

### Online Documentation

Documentation is automatically deployed to **GitLab Pages** on every push to the `master` branch.

## Project Structure

```
wildlife_pictures_extraction/
├── __init__.py                    # Package initialization
├── WildlifePictureExtractor.py    # Main class
├── MicrosoftGraphApi.py           # Microsoft Graph API client
├── DBManager.py                   # Database manager
├── pyproject.toml                 # Poetry configuration & metadata
├── README.md                      # This file
├── .env                           # Environment variables (not versioned)
│
├── DTO/                           # Data Transfer Objects
│   ├── __init__.py
│   └── PictureDTO.py              # Image data structure
│
└── docs/                          # Sphinx documentation
    ├── Makefile                   # Build documentation (Linux)
    ├── make.bat                   # Build documentation (Windows)
    ├── source/
    │   ├── conf.py                # Sphinx configuration
    │   ├── index.rst              # Homepage
    │   └── api.rst                # API documentation
    └── build/                     # Generated documentation (not versioned)
```

## API & Modules

### `WildlifePictureExtractor`

**Main class** orchestrating image extraction and processing.

**Key Methods:**
- `__init__()`: Initializes DB and API connections
- `extract_images_information(image_bytes)`: Extracts animal type and timestamp via OCR
- `extract_filename_information(filename)`: Extracts camera ID and timestamp from filename
- `process_emails()`: Processes email attachments

**Attributes:**
- `database`: Connection to the database
- `graph_api`: Connection to the Microsoft Graph API
- `access_token`: Access token from the application to send HTTP request
- `reader`: EasyOCR Reader instance

### `MicrosoftGraphApi`

**Authentication client** for Microsoft Graph API using MSAL.

**Key Methods:**
- `__init__()`: Loads credentials from `.env`
- `get_access_token()`: Obtains an OAuth 2.0 access token

**Attributes:**
- `tenant_id`: Azure AD tenant ID
- `client_id`: Azure AD application client ID
- `client_secret`: Azure AD application client secret
- `authority`: Azure AD authority URL
- `scope`: List of scopes for API access
- `app`: MSAL `ConfidentialClientApplication` instance

### `DBManager`

**Database manager** for MariaDB/MySQL operations.

**Key Methods:**
- `__init__(host, user, password, database)`: Connection configuration
- `connect()`: Establishes connection
- `disconnect()`: Closes connection
- `get_all_pictures()`: Retrieves all images
- `get_picture_by_id(picture_id)`: Retrieves a picture by its ID
- `verify_device_id_exists(device_id)`: Verifies if a device ID exists
- `create_device(device_id, lat, lng)`: Creates a new device
- `insert_picture(filename, image_metadata, image_type, device_id, parsed_successfully, timestamp)`: Inserts image with metadata

**Attributes:**
- `conn`: Connection to the database
- `host`: Database host
- `user`: Database user
- `password`: Database password
- `database`: Database name

### `PictureDTO`

**Data Transfer Object** for images and metadata.

**Attributes:**
- `id_picture`: Unique identifier of the picture
- `filename`: Filename of the picture
- `image_metadata`: Metadata of the picture
- `image_type`: Type of image
- `device_id`: ID of the camera that took the picture
- `parsed_successfully`: Whether the picture was parsed successfully
- `timestamp`: Timestamp when the picture was taken

## CI/CD

The GitLab CI/CD pipeline automates the following tasks:

### Pipeline Stages

1. **Test** (all branches)
   - Sphinx documentation build
   - Compilation verification without errors
   
2. **Deploy**
   - Documentation generation
   - Publication to GitLab Pages

## Troubleshooting

### Error: "Access token acquisition failed"

**Possible Causes:**
- Incorrect Azure AD credentials in `.env`
- Graph API permissions not granted
- Missing admin consent

**Solution**: Verify your credentials and permissions in Azure AD.

### Error: "Database connection failed"

**Solution**: Verify that MariaDB/MySQL is running and credentials in `.env` are correct. Check you're connected to the OTH VPN (database only accessible if you're on the VPN)

### OCR Not Detecting Text

**Solutions:**
- Check image quality (resolution, contrast)