import requests


def delete_workflow_runs(repo_owner, repo_name, access_token):
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/actions/runs"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github.v3+json"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        workflow_runs = response.json()["workflow_runs"]

        for run in workflow_runs:
            run_id = run["id"]
            delete_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/actions/runs/{run_id}"
            delete_response = requests.delete(delete_url, headers=headers)
            delete_response.raise_for_status()
            print(f"Deleted workflow run with ID {run_id}")

    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    repo_owner = "careerswitch"
    repo_name = "market-calendar"
    access_token = "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"

    delete_workflow_runs(repo_owner, repo_name, access_token)



