
# URL: https://microsoft.github.io/fabric-cicd/0.2.0/
TITLE: fabric-cicd

HEADERS:
- Home
- Base Expectations ¶
- Supported Item Types ¶
- Installation ¶
- Basic Example ¶
CODE_BLOCK_COUNT: 2
FIRST_CODE_BLOCK:
```
pip
install
fabric-cicd
```

# URL: https://microsoft.github.io/fabric-cicd/0.2.0/about/
TITLE: About - fabric-cicd

HEADERS:
- About ¶
- Security ¶
- Reporting Security Issues ¶
- Preferred Languages ¶
- Policy ¶
- License ¶
- Get help ¶
CODE_BLOCK_COUNT: 1
FIRST_CODE_BLOCK:
```
MIT License

Copyright (c) Microsoft Corporation.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE
```

# URL: https://microsoft.github.io/fabric-cicd/0.2.0/changelog/
TITLE: Changelog - fabric-cicd

HEADERS:
- Changelog ¶
- v0.2.0 - February 16, 2026 ¶
- ✨ New Functionality ¶
- 🔧 Bug Fix ¶
- ⚡ Additional Optimizations ¶
- 📝 Documentation Update ¶
- v0.1.34 - January 20, 2026 ¶
- ✨ New Functionality ¶
- 🆕 New Items Support ¶
- 📝 Documentation Update ¶
- ⚡ Additional Optimizations ¶
- v0.1.33 - December 16, 2025 ¶
- ✨ New Functionality ¶
- ⚡ Additional Optimizations ¶
- 🔧 Bug Fix ¶
- v0.1.32 - December 03, 2025 ¶
- 🔧 Bug Fix ¶
- v0.1.31 - December 01, 2025 ¶
- ⚠️ Breaking Change ¶
- ✨ New Functionality ¶
- 🆕 New Items Support ¶
- 📝 Documentation Update ¶
- 🔧 Bug Fix ¶
- v0.1.30 - October 20, 2025 ¶
- ✨ New Functionality ¶
- 🆕 New Items Support ¶
- ⚡ Additional Optimizations ¶
- 🔧 Bug Fix ¶
- v0.1.29 - October 01, 2025 ¶
- ✨ New Functionality ¶
- 🆕 New Items Support ¶
- 🔧 Bug Fix ¶
- v0.1.28 - September 15, 2025 ¶
- ✨ New Functionality ¶
- 🔧 Bug Fix ¶
- v0.1.27 - September 05, 2025 ¶
- 🔧 Bug Fix ¶
- v0.1.26 - September 05, 2025 ¶
- ⚠️ Breaking Change ¶
- ✨ New Functionality ¶
- 📝 Documentation Update ¶
- ⚡ Additional Optimizations ¶
- 🔧 Bug Fix ¶
- v0.1.25 - August 19, 2025 ¶
- ⚠️ Breaking Change ¶
- ✨ New Functionality ¶
- 📝 Documentation Update ¶
- ⚡ Additional Optimizations ¶
- 🔧 Bug Fix ¶
- v0.1.24 - August 04, 2025 ¶
- ⚠️ Breaking Change ¶
- 📝 Documentation Update ¶
- ⚡ Additional Optimizations ¶
- 🔧 Bug Fix ¶
- v0.1.23 - July 08, 2025 ¶
- ✨ New Functionality ¶
- 📝 Documentation Update ¶
- 🔧 Bug Fix ¶
- v0.1.22 - June 25, 2025 ¶
- 🆕 New Items Support ¶

# URL: https://microsoft.github.io/fabric-cicd/0.2.0/code_reference/
TITLE: Code Reference - fabric-cicd

HEADERS:
- Code Reference ¶
- FabricWorkspace ¶
- base_api_url property ¶
- FeatureFlag ¶
- CONTINUE_ON_SHORTCUT_FAILURE class-attribute instance-attribute ¶
- DISABLE_PRINT_IDENTITY class-attribute instance-attribute ¶
- DISABLE_WORKSPACE_FOLDER_PUBLISH class-attribute instance-attribute ¶
- ENABLE_ENVIRONMENT_VARIABLE_REPLACEMENT class-attribute instance-attribute ¶
- ENABLE_EVENTHOUSE_UNPUBLISH class-attribute instance-attribute ¶
- ENABLE_EXCLUDE_FOLDER class-attribute instance-attribute ¶
- ENABLE_EXPERIMENTAL_FEATURES class-attribute instance-attribute ¶
- ENABLE_ITEMS_TO_INCLUDE class-attribute instance-attribute ¶
- ENABLE_KQLDATABASE_UNPUBLISH class-attribute instance-attribute ¶
- ENABLE_LAKEHOUSE_UNPUBLISH class-attribute instance-attribute ¶
- ENABLE_RESPONSE_COLLECTION class-attribute instance-attribute ¶
- ENABLE_SHORTCUT_EXCLUDE class-attribute instance-attribute ¶
- ENABLE_SHORTCUT_PUBLISH class-attribute instance-attribute ¶
- ENABLE_SQLDATABASE_UNPUBLISH class-attribute instance-attribute ¶
- ENABLE_WAREHOUSE_UNPUBLISH class-attribute instance-attribute ¶
- ItemType ¶
- append_feature_flag ¶
- change_log_level ¶
- deploy_with_config ¶
- publish_all_items ¶
- unpublish_all_orphan_items ¶
CODE_BLOCK_COUNT: 20
FIRST_CODE_BLOCK:
```
FabricWorkspace
(
repository_directory
:
str
,
item_type_in_scope
:
Optional
[
list
[
str
]]
=
None
,
environment
:
str
=
"N/A"
,
workspace_id
:
Optional
[
str
]
=
None
,
workspace_name
:
Optional
[
str
]
=
None
,
token_credential
:
TokenCredential
=
None
,
**
kwargs
,
)
```

# URL: https://microsoft.github.io/fabric-cicd/0.2.0/example/
TITLE: Examples - fabric-cicd

HEADERS:
- How To ¶
- Contents ¶

# URL: https://microsoft.github.io/fabric-cicd/0.2.0/example/authentication/
TITLE: Authentication - fabric-cicd

HEADERS:
- Authentication Examples ¶
- Default Credential ¶
- CLI Credential ¶
- AZ PowerShell Credential ¶
- Explicit SPN Secret Credential ¶
CODE_BLOCK_COUNT: 16
FIRST_CODE_BLOCK:
```
'''Log in with Azure CLI (az login) or Azure PowerShell (Connect-AzAccount) prior to execution'''
from
pathlib
import
Path
from
fabric_cicd
import
FabricWorkspace
,
publish_all_items
,
unpublish_all_orphan_items
# Assumes your script is one level down from root
root_directory
=
Path
(
__file__
)
.
resolve
()
.
parent
# Sample values for FabricWorkspace parameters
workspace_id
=
"your-workspace-id"
environment
=
"your-environment"
repository_directory
=
str
(
root_directory
/
"your-workspace-directory"
)
item_type_in_scope
=
[
"Notebook"
,
"DataPipeline"
,
"Environment"
]
# Initialize the FabricWorkspace object with the required parameters
target_workspace
=
FabricWorkspace
(
workspace_id
=
workspace_id
,
environment
=
environment
,
repository_directory
=
repository_directory
,
item_type_in_scope
=
item_type_in_scope
,
)
# Publish all items defined in item_type_in_scope
publish_all_items
(
target_workspace
)
# Unpublish all items defined in item_type_in_scope not found in repository
unpublish_all_orphan_items
(
target_workspace
)
```

# URL: https://microsoft.github.io/fabric-cicd/0.2.0/example/deployment_variable/
TITLE: Deployment Variables - fabric-cicd

HEADERS:
- Deployment Variable Examples ¶
- Branch Based ¶
- Passed Arguments ¶
CODE_BLOCK_COUNT: 6
FIRST_CODE_BLOCK:
```
'''Leverages Default Credential Flow for authentication. Determines variables based on locally checked out branch.'''
from
pathlib
import
Path
import
git
# Depends on pip install gitpython
from
fabric_cicd
import
FabricWorkspace
,
publish_all_items
,
unpublish_all_orphan_items
# Assumes your script is one level down from root
root_directory
=
Path
(
__file__
)
.
resolve
()
.
parent
repo
=
git
.
Repo
(
root_directory
)
repo
.
remotes
.
origin
.
pull
()
branch
=
repo
.
active_branch
.
name
# The defined environment values should match the names found in the parameter.yml file
if
branch
==
"dev"
:
workspace_id
=
"dev-workspace-id"
environment
=
"DEV"
elif
branch
==
"main"
:
workspace_id
=
"prod-workspace-id"
environment
=
"PROD"
else
:
raise
ValueError
(
"Invalid branch to deploy from"
)
# Sample values for FabricWorkspace parameters
repository_directory
=
str
(
root_directory
/
"your-workspace-directory"
)
item_type_in_scope
=
[
"Notebook"
,
"DataPipeline"
,
"Environment"
]
# Initialize the FabricWorkspace object with the required parameters
target_workspace
=
FabricWorkspace
(
workspace_id
=
workspace_id
,
environment
=
environment
,
repository_directory
=
repository_directory
,
item_type_in_scope
=
item_type_in_scope
,
)
# Publish all items defined in item_type_in_scope
publish_all_items
(
target_workspace
)
# Unpublish all items defined in item_type_in_scope not found in repository
unpublish_all_orphan_items
(
target_workspace
)
```

# URL: https://microsoft.github.io/fabric-cicd/0.2.0/example/release_pipeline/
TITLE: Release Pipelines - fabric-cicd

HEADERS:
- Release Pipeline Examples ¶
- Azure CLI ¶
- Azure PowerShell ¶
- Variable Groups ¶
CODE_BLOCK_COUNT: 6
FIRST_CODE_BLOCK:
```
trigger:
branches:
include:
- dev
- main
stages:
- stage: Build_Release
jobs:
- job: Build
pool:
vmImage: windows-latest
steps:
- checkout: self
- task: UsePythonVersion@0
inputs:
versionSpec: '3.12'
addToPath: true
- script: |
pip install fabric-cicd
displayName: 'Install fabric-cicd'
- task: AzureCLI@2
displayName: "Deploy Fabric Workspace"
inputs:
azureSubscription: "your-service-connection"
scriptType: "ps"
scriptLocation: "inlineScript"
inlineScript: |
python -u $(System.DefaultWorkingDirectory)/.deploy/fabric_workspace.py
```

# URL: https://microsoft.github.io/fabric-cicd/0.2.0/how_to/
TITLE: How To - fabric-cicd

HEADERS:
- How To ¶
- Contents ¶

# URL: https://microsoft.github.io/fabric-cicd/0.2.0/how_to/config_deployment/
TITLE: Configuration Deployment - fabric-cicd

HEADERS:
- Configuration Deployment ¶
- Overview ¶
- Configuration File Setup ¶
- Core Settings ¶
- Publish Settings ¶
- Unpublish Settings ¶
- Features Setting ¶
- Constants Setting ¶
- Environment-Specific Values ¶
- Required vs Optional Fields ¶
- Selective Environment Configuration ¶
- Logging Behavior ¶
- Sample config.yml File ¶
- Configuration File Deployment ¶
- Basic Usage ¶
- Custom Authentication ¶
- Configuration Override ¶
- Troubleshooting Guide ¶
CODE_BLOCK_COUNT: 20
FIRST_CODE_BLOCK:
```
C:/dev/workspace
/HelloWorld.Notebook
...
/GoodbyeWorld.Notebook
...
/config.yml
```

# URL: https://microsoft.github.io/fabric-cicd/0.2.0/how_to/getting_started/
TITLE: Getting Started - fabric-cicd

HEADERS:
- Getting Started ¶
- Installation ¶
- Authentication ¶
- Directory Structure ¶
- GIT Flow ¶
CODE_BLOCK_COUNT: 2
FIRST_CODE_BLOCK:
```
pip
install
fabric-cicd
```

# URL: https://microsoft.github.io/fabric-cicd/0.2.0/how_to/item_types/
TITLE: Item Types - fabric-cicd

HEADERS:
- Item Types ¶
- Activator ¶
- Apache Airflow Job ¶
- API for GraphQL ¶
- Copy Job ¶
- Dataflow ¶
- Data Agent ¶
- Data Pipeline ¶
- Environment ¶
- Eventhouse ¶
- Eventstream ¶
- KQL Database ¶
- KQL Queryset ¶
- Lakehouse ¶
- Mirrored Database ¶
- ML Experiment ¶
- Mounted Data Factory ¶
- Notebook ¶
- Real-Time Dashboard ¶
- Report ¶
- Semantic Model ¶
- Spark Job Definition ¶
- SQL Database ¶
- User Data Function ¶
- Variable Library ¶
- Warehouse ¶

# URL: https://microsoft.github.io/fabric-cicd/0.2.0/how_to/optional_feature/
TITLE: Optional Features - fabric-cicd

HEADERS:
- Optional Features ¶
- Feature Flags ¶
- Debugging ¶
CODE_BLOCK_COUNT: 2
FIRST_CODE_BLOCK:
```
from
fabric_cicd
import
append_feature_flag
append_feature_flag
(
"enable_lakehouse_unpublish"
)
append_feature_flag
(
"enable_warehouse_unpublish"
)
append_feature_flag
(
"disable_print_identity"
)
append_feature_flag
(
"enable_environment_variable_replacement"
)
append_feature_flag
(
"enable_response_collection"
)
```

# URL: https://microsoft.github.io/fabric-cicd/0.2.0/how_to/parameterization/
TITLE: Parameterization - fabric-cicd

HEADERS:
- Parameterization ¶
- Overview ¶
- Parameter Inputs ¶
- find_replace ¶
- key_value_replace ¶
- spark_pool ¶
- semantic_model_binding ¶
- Advanced Find and Replace ¶
- find_value Regex ¶
- Dynamic Replacement ¶
- Environment Variable Replacement ¶
- File Filters ¶
- _ALL_ Environment Key in replace_value ¶
- Optional Fields ¶
- Regex Pattern Match ¶
- Supported File Filters ¶
- Parameter File Validation ¶
- Parameter File Templates ¶
- Sample Parameter File ¶
- Examples by Item Type ¶
- Notebooks ¶
- Data Pipelines ¶
- Schedules ¶
- Environments ¶
- Dataflows ¶
- Reports ¶
CODE_BLOCK_COUNT: 20
FIRST_CODE_BLOCK:
```
from
fabric_cicd
import
FabricWorkspace
workspace
=
FabricWorkspace
(
workspace_id
=
"your-workspace-id"
,
repository_directory
=
"C:/dev/workspace"
,
item_type_in_scope
=
[
"Notebook"
]
)
```

# URL: https://microsoft.github.io/fabric-cicd/0.2.0/how_to/troubleshooting/
TITLE: Troubleshooting - fabric-cicd

HEADERS:
- Troubleshooting ¶
- Debugging Deployments ¶
- Enable Debug Logging ¶
- Testing Deployments Locally ¶
- Sample Workspace Directory ¶
- Understanding Error Logs ¶
- Common Issues and Solutions ¶
- Debug Scripts ¶
- Getting Help ¶
- Additional Resources ¶
CODE_BLOCK_COUNT: 7
FIRST_CODE_BLOCK:
```
from
fabric_cicd
import
change_log_level
# Enable debug logging (call before other fabric-cicd operations)
change_log_level
()
```

# URL: https://microsoft.github.io/fabric-cicd/0.2.0/docs/how_to/troubleshooting.md
TITLE: 404 Not Found

HEADERS:
- 404 - Page Not Found