pipeline {
  agent any
  stages {
    stage('Checkout') {
      steps {
        checkout scm
      }
    }
    stage('Setup python venv'){
        steps {
          sh (label: 'setup-venv', script: '''
          bash -lc '
          set -euo pipefail
          echo "Hello from Jenkins on $(hostname)"
          git rev-parse --short HEAD
          ls -la
          echo "Setting up python venv and installing dependencies"
          python3 --version
          
          if [ ! -d .netbox-venv ]; then
            python3 -m venv .netbox-venv
          fi

          . .netbox-venv/bin/activate
          python3 -m pip install --upgrade pip wheel setuptools

          if [ -f requirements.txt ]; then
            pip install -r requirements.txt
          else
            echo "ERROR: requirements.txt file not found"
            exit 1
          fi
        '
        '''
        )
        }
    }
    stage('WAN scripts'){
        environment {
            NETBOX_URL = credentials('NETBOX_URL')
            API_TOKEN = credentials('API_TOKEN')
        }
        steps {
            sh (label: 'Setup', script: '''
            bash -lc '
            set -euo pipefail
            . .netbox-venv/bin/activate
            echo "Running WAN IP reconcilation scripts"
            python3 ./scripts/netbox_ping.py
            '
            '''
            )
        }
    }
    }
  }