DEPLOYMENT_TEMPLATE = {
  "apiVersion":"apps/v1",
  "kind":"Deployment",
  "metadata":{"name":"app"},
  "spec":{
    "replicas":1,
    "selector":{"matchLabels":{"app":"app"}},
    "template":{
      "metadata":{"labels":{"app":"app"}},
      "spec":{"containers":[{"name":"app","image":"nginx:latest"}]}
    }
  }
}

SERVICE_TEMPLATE = {
  "apiVersion":"v1",
  "kind":"Service",
  "metadata":{"name":"app"},
  "spec":{"selector":{"app":"app"},"ports":[{"port":80,"targetPort":80}]}
}
