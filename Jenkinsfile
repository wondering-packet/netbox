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
          python3 -m pip install --upgrade pip wheel setuptools # a standard command to upgrade pip and related tools before installing dependencies.

          # install dependency. another bash if statement. '-f' checks for file.
          if [ -f requirements.txt ]; then
            pip install -r requirements.txt
          else
            echo "ERROR: requirements.txt file not found"
            exit 1
          fi

        '''
        )
        }
    }
    // next stage. running scripts here.
    stage('WAN scripts'){
        environment {
            // setting env variables for this stage. we will use these in the script.
            NETBOX_URL = credentials('NETBOX_URL')
            NETBOX_TOKEN = credentials('NETBOX_TOKEN')
            RUN_ID = "${env.BUILD_ID}"  // using jenkins build id in scripts later for logging/tracking.
        }
        steps {
            sh (label: 'connectinvity test + reconcilation + cleanup', script: '''#!/bin/bash
            set -euo pipefail
            . .netbox-venv/bin/activate
            echo "\nStep 1: Running netbox connectivity test script"
            python3 ./scripts/netbox_ping.py

            echo "\nStep 2: Running WAN IP reconcilation script"
            python3 ./scripts/ingest_wan_ip.py

            echo "\nStep 3: Running cleanup script"
            python3 ./scripts/clean_deprecated_wan_ip.py
            '''
            )
        }
    }
    }
  
  post {
    always {
      echo "\nPipeline completed. Collecting artifacts."
      archiveArtifacts artifacts: "artifacts/${env.BUILD_ID}/**,artifacts-cleanup/${env.BUILD_ID}/**",
      allowEmptyArchive: true,
      fingerprint: true
    }
  }
}