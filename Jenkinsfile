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
          sh (label: 'sanity', script: '''
          bash -lc '
          set -euo pipefail
          echo "Hello from Jenkins on $(hostname)"
          git rev-parse --short HEAD
          ls -la
          echo "Setting up python venv and installing dependencies"
          python3 --version
          # create/use existing venv
          if [ ! -d .netbox-venv ]; then
            python3 -m venv .netbox-venv
          fi

          . .netbox-venv/bin/activate
          python3 -m pip install --upgrade pip wheel setuptools

          # install dependency
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
        steps {
            sh (label: 'Setup', script: '''#!/bin/bash -euo pipefail
            . .netbox-venv/bin/activate
            echo "Running WAN IP reconcilation scripts"
            # netbox connectivity test
            python3 ./scripts/netbox_ping.py
            '''
            )
        }
    }
    }
  }
