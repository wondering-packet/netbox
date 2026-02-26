// bash is new to me. just adding a few comments for easier understanding. code is generated with the help of chatgpt.

pipeline {
  agent any     // run this pipeline on any executor.
    // stages are the high level steps. each stage can have multiple steps.
  stages {
    // a standard 'checkout' stage. this checks out the git repo locally.
    stage('Checkout') {
      steps {
        checkout scm
      }
    }
    // setting up python & the venv.
    stage('Setup python venv'){
        steps {
            // 'sh' is our linux bash command runner. label is just an identifier for the step.
          sh (label: 'setup-venv', script: '''#!/bin/bash

          set -euo pipefail # this is a common set of bash options to make the script more robust. it means:
                          # -e: exit immediately if a command exits with a non-zero status.
                          # -u: treat unset variables as an error and exit immediately.
                          # -o pipefail: if any command in a pipeline fails, that return code will be used as the return code of the whole pipeline.
          echo "Hello from Jenkins on $(hostname)"
          git rev-parse --short HEAD    # prints out the current commit hash.
          ls -la    # optional; list directory contents.
          echo "Setting up python venv and installing dependencies"
          python3 --version
          # create/use existing venv
          # bash logic. starts with 'if' ends with 'fi'.
          if [ ! -d .netbox-venv ]; then    # if the directory (-d) doesn't (!) exist, then create the venv.
            python3 -m venv .netbox-venv
          fi

          . .netbox-venv/bin/activate   # activate the venv. we will be using this same venv for all stages.
          .netbox-venv/bin/python -m pip install --upgrade pip wheel setuptools # a standard command to upgrade pip and related tools before installing dependencies.

          # install dependency. another bash if statement. '-f' checks for file.
          if [ -f requirements.txt ]; then
            .netbox-venv/bin/python -mpip install -r requirements.txt
          else
            echo "ERROR: requirements.txt file not found"
            exit 1
          fi

        '''
        )
        }
    }
    // next stage. running scripts here.
    stage('Reconcilation') {
        environment {
            // setting env variables for this stage. we will use these in the script.
            NETBOX_URL = credentials('NETBOX_URL')
            NETBOX_TOKEN = credentials('NETBOX_TOKEN')
            RUN_ID = "${env.BUILD_ID}"  // using jenkins build id in scripts later for logging/tracking.
        }
        steps {
            sh (label: 'connectinvity test + reconcilation', script: '''#!/bin/bash
            set -euo pipefail
            . .netbox-venv/bin/activate
            echo "\nStep 1: Running netbox connectivity test script"
            python3 ./scripts/netbox_ping.py

            echo "\nStep 2: Running WAN IP reconcilation script"
            python3 ./scripts/ingest_wan_ip.py
            '''
            )
        }
    }

    stage('Artifacts Offloading') {
        environment {
            RUN_ID = "${env.BUILD_ID}"
        }
        steps {
            sh (label: 'Offloading artifacts to jenkins smb share', script: '''#!/bin/bash
            set -euo pipefail
            DEST="/mnt/jenkins-artifacts/${JOB_NAME}/${RUN_ID}"
            mkdir -p "$DEST"
            [ -d "artifacts/${RUN_ID}" ] && rsync -a "artifacts/${RUN_ID}/" "$DEST/artifacts/"
            [ -d "artifacts-cleanup/${RUN_ID}" ] && rsync -a "artifacts-cleanup/${RUN_ID}/" "$DEST/artifacts-cleanup/"

            echo "Artifacts offloaded to $DEST. Contents:"
            ls -la "$DEST"
            '''
            )
        }
    }
    }
  
  post {
    always {
      // cleaning up the workspace
      cleanWs()
  }
}
}