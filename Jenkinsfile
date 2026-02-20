pipeline {
  agent any

  stages {
    stage('Checkout') {
      steps {
        checkout scm
      }
    }

    stage('Sanity') {
      steps {
        sh '''
          set -euxo pipefail
          echo "Hello from Jenkins on $(hostname)"
          git rev-parse --short HEAD
          ls -la
        '''
      }
    }
  }
}
