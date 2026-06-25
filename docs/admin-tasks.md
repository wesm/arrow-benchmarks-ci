## Admin Tasks

Admin Tasks can only performed by a contributor who has access to AWS account running Arrow Benchmarks CI and
[Apache Arrow Buildkite Org](https://buildkite.com/organizations/apache-arrow) user.

### Create ARROW_BCI_API_ACCESS_TOKEN for Benchmark Machine
```shell script
kubectl exec -it deploy/arrow-bci-deployment bash
root@arrow-bci-deployment-75f67db476-vcth8:/app# python
Python 3.8.12 (default, Oct 13 2021, 09:15:35)
[GCC 10.2.1 20210110] on linux
Type "help", "copyright", "credits" or "license" for more information.
>>> from models.machine import Machine
>>> Machine(name='new-machine').create_api_access_token()
```

### Create BUILDKITE_AGENT_TOKEN for Benchmark Machine
- Go to https://buildkite.com/organizations/apache-arrow/settings
- Copy `Organization ID` under GraphQL API Integration so you can use it in the next step
- Go to https://buildkite.com/user/graphql/console
- Paste this query, replacing `Organization ID` with your Organization ID
```
mutation {
  agentTokenCreate(input: {
    organizationID: "Organization ID",
    description: "BK agent token for Benchmark Machine X"
  }) {
    agentTokenEdge {
      node {
        id
        token
      }
    }
  }
}
```
- click Execute
- Copy token from results
```
{
  "data": {
    "agentTokenCreate": {
      "agentTokenEdge": {
        "node": {
          "id": "xxx",
          "token": "copy-this-value"
        }
      }
    }
  }
}
```

### Create CONBENCH_TOKEN for Benchmark Machine
- Mint a Conbench API token for the benchmark reporter.
- Store the plaintext token as `CONBENCH_TOKEN` in the benchmark machine
  environment or Buildkite queue secret.

### Create ec2 benchmark machine
- Go to https://us-east-1.console.aws.amazon.com/ec2/v2/home?region=us-east-1#Instances:
- Click Launch instance from template
- Source template = benchmark-machine
- Select Instance type that you need
- Click Launch instance from template
- Go to launched ec2 instance > click Connect > click Connect
- Follow "Step 3. Setup your benchmark machine" in [How to Add New Benchmark Machine](how-to-add-new-benchmark-machine-for-running-apache-arrow-benchmarks.md)
