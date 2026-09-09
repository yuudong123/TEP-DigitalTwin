pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Prepare deployment environment') {
            steps {
                withCredentials([
                    file(
                        credentialsId: 'tep-development-env',
                        variable: 'DEPLOY_ENV_FILE'
                    )
                ]) {
                    sh '''
                        install -m 600 "$DEPLOY_ENV_FILE" .env
                    '''
                }
            }
        }

        stage('Validate deployment configuration') {
            steps {
                sh '''
                    set -eu
                    test -f compose.yaml
                    test -f .env
                    docker compose config --quiet
                '''
            }
        }

        stage('Run tests') {
            steps {
                script {
                    if (!fileExists('.venv/bin/python')) {
                        echo 'Skipping tests: project .venv is not available on this agent.'
                    } else if (!fileExists('tests')) {
                        echo 'Skipping tests: tests directory has not been added yet.'
                    } else {
                        int hasTests = sh(
                            script: "find tests -type f -name 'test_*.py' -print -quit | grep -q .",
                            returnStatus: true
                        )

                        if (hasTests != 0) {
                            echo 'Skipping tests: no pytest test files were found.'
                        } else {
                            sh '.venv/bin/python -m pytest tests'
                        }
                    }
                }
            }
        }

        stage('Build Docker images') {
            when {
                branch 'dev'
            }
            steps {
                sh 'docker compose build'
            }
        }

        stage('Deploy to development server') {
            when {
                branch 'dev'
            }
            steps {
                sh '''
                    set -eu
                    docker compose up --detach
                    docker compose ps --all
                '''
            }
        }
    }

    post {
        always {
            sh 'rm -f .env'
        }
        failure {
            sh 'docker compose ps --all || true'
            sh 'docker compose logs --tail 100 || true'
        }
    }
}
