pipeline {
    agent { label 'tep-windows' }
    options {
        timestamps()
        disableConcurrentBuilds()
        skipDefaultCheckout(true)
        timeout(time: 45, unit: 'MINUTES')
    }
    triggers { pollSCM('H/2 * * * *') }
    environment {
        TEP_RUNTIME_DIR = 'D:\\TEP_DigitalTwin'
        DOCKER_HOST = 'npipe:////./pipe/dockerDesktopLinuxEngine'
        PATH = "C:\\Program Files\\Git\\cmd;C:\\Program Files\\Docker\\Docker\\resources\\bin;${env.PATH}"
    }
    stages {
        stage('Checkout dev') {
            steps {
                checkout scmGit(
                    branches: [[name: '*/dev']],
                    extensions: [[$class: 'DisableRemotePoll']],
                    userRemoteConfigs: [[url: 'https://github.com/yuudong123/TEP-DigitalTwin.git']]
                )
                bat '@git log -1 --oneline'
            }
        }
        stage('Build and deploy on home PC') {
            steps {
                script {
                    int result = bat(returnStatus: true, script: '''@echo off
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%TEP_RUNTIME_DIR%\\deploy\\09-manual-deploy.ps1" -SourceDir "%WORKSPACE%" -RuntimeDir "%TEP_RUNTIME_DIR%"
exit /b %ERRORLEVEL%
''')
                    if (result == 2) {
                        unstable('Infrastructure deployed; application entrypoints are pending sections 12, 13 and 17. See deployment log.')
                    } else if (result != 0) {
                        error("Deployment failed (exit ${result}). See deployment log.")
                    }
                }
            }
        }
    }
}
