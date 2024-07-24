import argparse
import json
import requests
import yaml

from datetime import datetime
from jira import JIRA

from requests.auth import HTTPBasicAuth


def load_yaml(file_path):
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)

def connect_to_jira_server(config):
    JIRA_SERVER = 'https://rubrik.atlassian.net'
    jira_options = {'server': JIRA_SERVER}
    JIRA_USER = config["UserInfo"]["email_id"]
    JIRA_API_TOKEN = config["UserInfo"]["jira_api_token"]
    # JIRA Authentication
    jira = JIRA(options=jira_options, basic_auth=(JIRA_USER, JIRA_API_TOKEN))
    return jira

def extract_data_from_jira_query(jira_server, query):
    issues = jira_server.search_issues(query, maxResults=False)
    # Data Processing
    report_data = {
        'total_issues_resolved': len(issues),
        'components': {},
        'resolutions': {},
        'root_cause_labels': {},
        'actual_root_cause_labels': {},
        'issues': []
    }

    # Convert list of list to normal
    tmpRootCauseLabels = [issue.fields.customfield_13328 for issue in issues]
    rootCauseLabels = []
    for a_list in tmpRootCauseLabels:
        if a_list != None:
            rootCauseLabels.append(a_list[0])

    # Aggregate root cause labels
    for a_label in rootCauseLabels:
        if a_label not in report_data['actual_root_cause_labels'] and a_label != None:
            report_data['actual_root_cause_labels'][a_label] = 0


    print(f"root_cause_labels: {rootCauseLabels}")

    for issue in issues:
        # Extract relevant fields
        components = [component.name for component in issue.fields.components]
        resolution = issue.fields.resolution.name
        labels = issue.fields.labels
        if issue.fields.customfield_13328 != None:
            jiraSpecificRootCauseLable = issue.fields.customfield_13328[0]
        else:
            jiraSpecificRootCauseLable = None

        # Populate report data
        report_data['issues'].append({
            'key': issue.key,
            'summary': issue.fields.summary,
            'assignee': issue.fields.assignee.displayName if issue.fields.assignee else 'Unassigned',
            'priority': issue.fields.priority.name,
            'status': issue.fields.status.name,
            'updated': issue.fields.updated,
            'resolution': resolution,
            'components': components,
            'labels': labels,
            'root_cause_labels': issue.fields.customfield_13328,
        })

        # Aggregate components
        for component in components:
            if component not in report_data['components']:
                report_data['components'][component] = 0
            report_data['components'][component] += 1

        # Aggregate resolutions
        if resolution not in report_data['resolutions']:
            report_data['resolutions'][resolution] = 0
        report_data['resolutions'][resolution] += 1

        # Aggregate labels
        for label in labels:
            if label not in report_data['root_cause_labels']:
                report_data['root_cause_labels'][label] = 0
            report_data['root_cause_labels'][label] += 1

        # Aggregate root cause labels
        if jiraSpecificRootCauseLable != None:
            report_data['actual_root_cause_labels'][jiraSpecificRootCauseLable] += 1

    # Generate Report (Print to console or save to a file)
    current_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_filename = f'CLA_Report_{current_timestamp}_created_post.json'
    with open(report_filename, 'w') as report_file:
        json.dump(report_data, report_file, indent=4)

    print(f'Report generated: {report_filename}')
    return report_data

def update_confluence_page(config,new_content):
    CONFLUENCE_URL = 'https://rubrik.atlassian.net/wiki/'
    PAGE_ID = config["ConfluenceInfo"]["page_id"]
    USERNAME = config["UserInfo"]["email_id"]
    API_TOKEN = config["UserInfo"]["jira_api_token"]

        # Get the current page version
    url = f'{CONFLUENCE_URL}/rest/api/content/{PAGE_ID}'

    response = requests.get(url, auth=HTTPBasicAuth(USERNAME, API_TOKEN))
    response.raise_for_status()
    page_data = response.json()
    current_version = page_data['version']['number']

    # Update the page with new content
    update_url = f'{CONFLUENCE_URL}/rest/api/content/{PAGE_ID}'

    # Create payload for updating the page
    payload = {
        'id': PAGE_ID,
        'type': 'page',
        'title': page_data['title'],
        'version': {'number': current_version + 1},
        'body': {
            'storage': {
                'value': new_content,
                'representation': 'storage'
            }
        }
    }

    # Send the update request
    headers = {
        'Content-Type': 'application/json'
    }
    update_response = requests.put(
        update_url,
        data=json.dumps(payload),
        headers=headers,
        auth=HTTPBasicAuth(USERNAME, API_TOKEN)
    )
    update_response.raise_for_status()

    print('Page updated successfully.')

def generateContentMssql(config,data):
    sorted_root_cause_lables = sorted(data["actual_root_cause_labels"], key=data["actual_root_cause_labels"].get, reverse=True)
    sorted_resolution = sorted(data["resolutions"], key=data["resolutions"].get, reverse=True)
    total_issues = data["total_issues_resolved"]

    jira_query_url = config["QueryInfo"]["jira_query_url"]
    issue_specific_jql_url = []
    for i in range(0,4):
        issue_specific_jql_url.append(jira_query_url + sorted_root_cause_lables[i])
        print(issue_specific_jql_url[i])


    # New content to update the page
    new_content = f"""
    <h1>Summary</h1>
    <p>Total issues resolved: {total_issues} </p>
    <h2>Top Component Areas for CFD: </h2>

    <table>
        <tr>
            <th>Root Cause Labels</th>
            <th>Issue Count</th>
        </tr>
        <tr>
            <td>{sorted_root_cause_lables[0]}</td>
            <td>{data["actual_root_cause_labels"][sorted_root_cause_lables[0]]} - {data["actual_root_cause_labels"][sorted_root_cause_lables[0]]*100/total_issues:.2f} %</td>
        </tr>
        <tr>
            <td>{sorted_root_cause_lables[1]}</td>
            <td>{data["actual_root_cause_labels"][sorted_root_cause_lables[1]]} - {data["actual_root_cause_labels"][sorted_root_cause_lables[1]]*100/total_issues:.2f} %</td>
        </tr>
        <tr>
            <td>{sorted_root_cause_lables[2]}</td>
            <td>{data["actual_root_cause_labels"][sorted_root_cause_lables[2]]} - {data["actual_root_cause_labels"][sorted_root_cause_lables[2]]*100/total_issues:.2f} %</td>
        </tr>
        <tr>
            <td>{sorted_root_cause_lables[3]}</td>
            <td>{data["actual_root_cause_labels"][sorted_root_cause_lables[3]]} - {data["actual_root_cause_labels"][sorted_root_cause_lables[0]]*100/total_issues:.2f} %</td>
        </tr>
    </table>

    <h2> Top Resolution Types for CFD’s: </h2>

    <table>
        <tr>
            <th>Resolution</th>
            <th>Issue Count</th>
        </tr>
        <tr>
            <td>{sorted_resolution[0]}</td>
            <td>{data["resolutions"][sorted_resolution[0]]} - {data["resolutions"][sorted_resolution[0]]*100/total_issues:.2f} %</td>
        </tr>
        <tr>
            <td>{sorted_resolution[1]}</td>
            <td>{data["resolutions"][sorted_resolution[1]]} - {data["resolutions"][sorted_resolution[1]]*100/total_issues:.2f} %</td>
        </tr>
        <tr>
            <td>{sorted_resolution[2]}</td>
            <td>{data["resolutions"][sorted_resolution[2]]} - {data["resolutions"][sorted_resolution[2]]*100/total_issues:.2f} %</td>
        </tr>
    </table>

    <!-- Page Break -->
    <div style="page-break-after: always;"></div>

    <h3> Total resolved issues </h3>

    <!-- Expand Section with JIRA Query -->
    <ac:structured-macro ac:name="expand">
    <ac:parameter ac:name="title">JIRA Issues</ac:parameter>
    <ac:rich-text-body>
            <a href="{config["QueryInfo"]["jira_query_url"]}"
        data-card-appearance="block">
        {config["QueryInfo"]["jira_query_url"]}
    </a>
    </ac:rich-text-body>
    </ac:structured-macro>

    <h1>CFDs by component Area</h1>
    <h2> Add Image </h2>
    <ul>
        <li> {sorted_root_cause_lables[0]} ({data["actual_root_cause_labels"][sorted_root_cause_lables[0]]*100/total_issues:.2f} %) </li>
    </ul>
            <!-- Expand Section with JIRA Query -->
            <ac:structured-macro ac:name="expand">
            <ac:parameter ac:name="title">{sorted_root_cause_lables[0]} issues</ac:parameter>
            <ac:rich-text-body>
            <a href="{str(issue_specific_jql_url[0])}"
                data-card-appearance="block" >
                "{str(issue_specific_jql_url[0])}"
            </a>
            </ac:rich-text-body>
            </ac:structured-macro>

        <ul>
            <li> {sorted_root_cause_lables[1]} ({data["actual_root_cause_labels"][sorted_root_cause_lables[1]]*100/total_issues:.2f} %) </li>
        </ul>
            <!-- Expand Section with JIRA Query -->
            <ac:structured-macro ac:name="expand">
            <ac:parameter ac:name="title">{sorted_root_cause_lables[1]} issues</ac:parameter>
            <ac:rich-text-body>
            <a href="{str(issue_specific_jql_url[1])}"
                data-card-appearance="block" >
                "{str(issue_specific_jql_url[1])}"
            </a>
            </ac:rich-text-body>
            </ac:structured-macro>


        <ul>
            <li> {sorted_root_cause_lables[2]} ({data["actual_root_cause_labels"][sorted_root_cause_lables[2]]*100/total_issues:.2f} %) </li>
        </ul>
        <!-- Expand Section with JIRA Query -->
        <ac:structured-macro ac:name="expand">
        <ac:parameter ac:name="title">{sorted_root_cause_lables[2]} issues</ac:parameter>
        <ac:rich-text-body>
        <a href="{str(issue_specific_jql_url[2])}"
            data-card-appearance="block" >
            "{str(issue_specific_jql_url[2])}"
        </a>
        </ac:rich-text-body>
        </ac:structured-macro>

        <ul>
            <li> {sorted_root_cause_lables[3]} ({data["actual_root_cause_labels"][sorted_root_cause_lables[3]]*100/total_issues:.2f} %) </li>
        </ul>
        <!-- Expand Section with JIRA Query -->
        <ac:structured-macro ac:name="expand">
        <ac:parameter ac:name="title">{sorted_root_cause_lables[3]} issues</ac:parameter>
        <ac:rich-text-body>
        <a href="{str(issue_specific_jql_url[3])}"
            data-card-appearance="block" >
            "{str(issue_specific_jql_url[3])}"
        </a>
        </ac:rich-text-body>
        </ac:structured-macro>


        <h1> Analysis based on Resolution type </h1>
        <h2> Add image</h2>

        <ul>
            <li> {sorted_resolution[0]} ({data["resolutions"][sorted_resolution[0]]*100/total_issues:.2f} %) </li>
        </ul>
        <!-- Expand Section with JIRA Query -->
        <ac:structured-macro ac:name="expand">
        <ac:parameter ac:name="title">{sorted_resolution[0]} issues</ac:parameter>
        <ac:rich-text-body>
        </ac:rich-text-body>
        </ac:structured-macro>

        <ul>
            <li> {sorted_resolution[1]} ({data["resolutions"][sorted_resolution[1]]*100/total_issues:.2f} %) </li>
        </ul>
        <!-- Expand Section with JIRA Query -->
        <ac:structured-macro ac:name="expand">
        <ac:parameter ac:name="title">{sorted_resolution[1]} issues</ac:parameter>
        <ac:rich-text-body>
        </ac:rich-text-body>
        </ac:structured-macro>

        <ul>
            <li> {sorted_resolution[2]} ({data["resolutions"][sorted_resolution[2]]*100/total_issues:.2f} %) </li>
        </ul>
        <!-- Expand Section with JIRA Query -->
        <ac:structured-macro ac:name="expand">
        <ac:parameter ac:name="title">{sorted_resolution[2]} issues</ac:parameter>
        <ac:rich-text-body>
        </ac:rich-text-body>
        </ac:structured-macro>



    """

    return new_content

def generateContentFileset():
    pass

def contentGenerator(config,data):
    component = config["ComponentInfo"]["name"]
    if component == 'mssql':
        return generateContentMssql(config,data)
    elif component == 'fileset':
        return generateContentFileset()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process some YAML config.')
    parser.add_argument(
        '--file_path',
        dest='file_path',
        type=str,
        help='Path to the YAML config file')

    args = parser.parse_args()

    config = load_yaml(args.file_path)
    jira_server = connect_to_jira_server(config=config)
    query = config["QueryInfo"]["jira_query"]
    extracted_data = extract_data_from_jira_query(
        jira_server=jira_server,
        query=query)

    new_content = contentGenerator(config,extracted_data)
    update_confluence_page(config,new_content)
    print(config)
