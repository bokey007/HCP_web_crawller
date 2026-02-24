pipeline {
    agent any

    environment {
        REGISTRY       = 'your-registry.example.com'
        IMAGE_NAME     = 'hcp-web-crawler'
        HELM_RELEASE   = 'hcp-crawler'
        OCP_NAMESPACE  = 'hcp-crawler'
        OCP_CLUSTER    = 'https://api.your-cluster.example.com:6443'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Lint') {
            steps {
                sh 'pip install uv && uv pip install --system ".[dev]"'
                sh 'ruff check src/ tests/'
            }
        }

        stage('Test') {
            steps {
                sh 'uv run pytest tests/ -v --tb=short --junitxml=test-results.xml'
            }
            post {
                always {
                    junit 'test-results.xml'
                }
            }
        }

        stage('Build Docker Image') {
            steps {
                script {
                    def tag = "${env.BUILD_NUMBER}-${env.GIT_COMMIT?.take(7) ?: 'latest'}"
                    env.IMAGE_TAG = tag
                    sh "docker build -t ${REGISTRY}/${IMAGE_NAME}:${tag} ."
                }
            }
        }

        stage('Push to Registry') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'registry-credentials',
                    usernameVariable: 'REG_USER',
                    passwordVariable: 'REG_PASS'
                )]) {
                    sh "docker login ${REGISTRY} -u ${REG_USER} -p ${REG_PASS}"
                    sh "docker push ${REGISTRY}/${IMAGE_NAME}:${env.IMAGE_TAG}"
                }
            }
        }

        stage('Deploy to OpenShift') {
            steps {
                withCredentials([string(
                    credentialsId: 'ocp-token',
                    variable: 'OCP_TOKEN'
                )]) {
                    sh """
                        oc login ${OCP_CLUSTER} --token=${OCP_TOKEN} --insecure-skip-tls-verify
                        helm upgrade --install ${HELM_RELEASE} ./helm \
                            --namespace ${OCP_NAMESPACE} \
                            --set image.repository=${REGISTRY}/${IMAGE_NAME} \
                            --set image.tag=${env.IMAGE_TAG} \
                            --wait --timeout 300s
                    """
                }
            }
        }
    }

    post {
        success {
            echo "✅ Pipeline succeeded — deployed ${IMAGE_NAME}:${env.IMAGE_TAG}"
        }
        failure {
            echo "❌ Pipeline failed"
        }
        always {
            cleanWs()
        }
    }
}
