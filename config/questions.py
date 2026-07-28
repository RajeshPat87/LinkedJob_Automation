'''
Author:     Sai Vignesh Golla
LinkedIn:   https://www.linkedin.com/in/saivigneshgolla/

Copyright (C) 2024 Sai Vignesh Golla

License:    GNU Affero General Public License
            https://www.gnu.org/licenses/agpl-3.0.en.html
            
GitHub:     https://github.com/GodsScion/Auto_job_applier_linkedIn

Support me: https://github.com/sponsors/GodsScion

version:    26.01.20.5.08
'''


###################################################### APPLICATION INPUTS ######################################################


# >>>>>>>>>>> Easy Apply Questions & Inputs <<<<<<<<<<<

# Give an relative path of your default resume to be uploaded. If file in not found, will continue using your previously uploaded resume in LinkedIn.
default_resume_path = "all resumes/default/resume.pdf"      # (In Development)

# What do you want to answer for questions that ask about years of experience you have, this is different from current_experience? 
years_of_experience = "14"         # A number in quotes Eg: "0","1","2","3","4", etc.

# Do you need visa sponsorship now or in future?
require_visa = "No"               # "Yes" or "No"

# What is the link to your portfolio website, leave it empty as "", if you want to leave this question unanswered
website = "https://github.com/RajeshPat87"                      # "www.example.bio" or "" and so on....

# Please provide the link to your LinkedIn profile.
linkedIn = "https://www.linkedin.com/in/rajesh-patibandla-devops"   # "https://www.linkedin.com/in/example" or "" and so on...

# What is the status of your citizenship? # If left empty as "", tool will not answer the question. However, note that some companies make it compulsory to be answered
# Valid options are: "U.S. Citizen/Permanent Resident", "Non-citizen allowed to work for any employer", "Non-citizen allowed to work for current employer", "Non-citizen seeking work authorization", "Canadian Citizen/Permanent Resident" or "Other"
us_citizenship = "Other"           # India-based, applying to Indian roles. Change to "Non-citizen seeking work authorization" only if you start targeting US jobs.



## SOME ANNOYING QUESTIONS BY COMPANIES 🫠 ##

# What to enter in your desired salary question (American and European), What is your expected CTC (South Asian and others)?, only enter in numbers as some companies only allow numbers,
desired_salary = 4000000          # 80000, 90000, 100000 or 120000 and so on... Do NOT use quotes
'''
Note: If question has the word "lakhs" in it (Example: What is your expected CTC in lakhs), 
then it will add '.' before last 5 digits and answer. Examples: 
* 2400000 will be answered as "24.00"
* 850000 will be answered as "8.50"
And if asked in months, then it will divide by 12 and answer. Examples:
* 2400000 will be answered as "200000"
* 850000 will be answered as "70833"
'''

# What is your current CTC? Some companies make it compulsory to be answered in numbers...
current_ctc = 3200000           # 800000, 900000, 1000000 or 1200000 and so on... Do NOT use quotes
'''
Note: If question has the word "lakhs" in it (Example: What is your current CTC in lakhs), 
then it will add '.' before last 5 digits and answer. Examples: 
* 2400000 will be answered as "24.00"
* 850000 will be answered as "8.50"
# And if asked in months, then it will divide by 12 and answer. Examples:
# * 2400000 will be answered as "200000"
# * 850000 will be answered as "70833"
'''

# (In Development) # Currency of salaries you mentioned. Companies that allow string inputs will add this tag to the end of numbers. Eg: 
# currency = "INR"                 # "USD", "INR", "EUR", etc.

# What is your notice period in days?
notice_period = 0                    # Any number >= 0 without quotes. Eg: 0, 7, 15, 30, 45, etc.
'''
Note: If question has 'month' or 'week' in it (Example: What is your notice period in months), 
then it will divide by 30 or 7 and answer respectively. Examples:
* For notice_period = 66:
  - "66" OR "2" if asked in months OR "9" if asked in weeks
* For notice_period = 15:"
  - "15" OR "0" if asked in months OR "2" if asked in weeks
* For notice_period = 0:
  - "0" OR "0" if asked in months OR "0" if asked in weeks
'''

# Your LinkedIn headline in quotes Eg: "Software Engineer @ Google, Masters in Computer Science", "Recent Grad Student @ MIT, Computer Science"
linkedin_headline = "Senior DevOps & Platform Engineer | Azure, AKS, Terraform, ArgoCD, GitOps | AZ-400 & FinOps Certified | 14+ Years" # "Headline" or "" to leave this question unanswered

# Your summary in quotes, use \n to add line breaks if using single quotes "Summary".You can skip \n if using triple quotes """Summary"""
linkedin_summary = """
DevOps and platform engineer with 14+ years across Azure, Kubernetes, and CI/CD. Six of those years were client-facing delivery lead roles for Citi Bank and a US health insurer, running distributed teams of up to 20 engineers.
Strongest hands-on in Terraform, Ansible, AKS, GitOps, and pipeline security. Built two platforms from scratch in 2026 and published both on GitHub: an Azure Landing Zone (management groups, Azure Policy governance, hub-and-spoke networking, subscription vending) and an AKS internal developer platform (ArgoCD GitOps, OPA Gatekeeper admission policy, External Secrets over workload identity).
Microsoft Certified DevOps Professional (AZ-400), AWS Cloud Practitioner, and FinOps Certified Practitioner. Use Claude Code and MCP daily for Terraform module authoring, Helm scaffolding, and first-pass incident analysis.
"""

'''
Note: If left empty as "", the tool will not answer the question. However, note that some companies make it compulsory to be answered. Use \n to add line breaks.
''' 

# Your cover letter in quotes, use \n to add line breaks if using single quotes "Cover Letter".You can skip \n if using triple quotes """Cover Letter""" (This question makes sense though)
cover_letter = """
Dear Hiring Team,

I am applying for this role as a Senior DevOps and Platform Engineer with 14+ years of experience across Azure, Kubernetes, and CI/CD, including six years as a client-facing delivery lead for Citi Bank and a US health insurance organization.

Most recently at DSV Global Transport & Logistics, I built reusable Terraform modules and Azure DevOps YAML pipelines that provisioned PostgreSQL Flexible Server across five environments, moved our pipelines to OIDC passwordless authentication to eliminate stored credentials, and delivered a Master DevOps Dashboard that consolidated MTTR and deployment-trend metrics from Azure DevOps, GitHub, JFrog, and SonarQube for leadership.

In 2026 I built and open-sourced two platforms end to end: an Azure Landing Zone in Terraform covering management-group hierarchy, Azure Policy governance, hub-and-spoke networking, and subscription vending; and an internal developer platform on AKS where ArgoCD runs GitOps, OPA Gatekeeper enforces admission policy, and External Secrets pulls from Key Vault over workload identity, so a developer commits one YAML file and gets a namespace, pipeline, TLS, and secrets without raising a ticket.

Alongside the hands-on work, I have led distributed teams of up to 20 engineers as Scrum Master and single point of contact, owning sprint planning, SLAs, risk management, and escalations. I hold AZ-400, AWS Cloud Practitioner, and FinOps Certified Practitioner certifications, and I am available to join immediately.

I would welcome the chance to discuss how I can contribute to your platform and delivery goals.

Sincerely,
Rajesh Patibandla
+91 7997282703 | rajeshsqldba87@gmail.com | github.com/RajeshPat87
"""
##> ------ Dheeraj Deshwal : dheeraj9811 Email:dheeraj20194@iiitd.ac.in/dheerajdeshwal9811@gmail.com - Feature ------

# Your user_information_all letter in quotes, use \n to add line breaks if using single quotes "user_information_all".You can skip \n if using triple quotes """user_information_all""" (This question makes sense though)
# We use this to pass to AI to generate answer from information , Assuing Information contians eg: resume  all the information like name, experience, skills, Country, any illness etc. 
user_information_all ="""
Name: Rajesh Patibandla
Title: Senior DevOps & Platform Engineer | Delivery Lead
Location: Hyderabad, Telangana, India (Indian citizen, no visa sponsorship required for India-based roles)
Contact: +91 7997282703 | rajeshsqldba87@gmail.com
Links: github.com/RajeshPat87 | linkedin.com/in/rajesh-patibandla-devops
Total experience: 14+ years. Notice period: immediately available. Education: MCA, JNTU Kakinada.
Languages: English, Hindi, Telugu. No disability. Male. Not a veteran.

SUMMARY
DevOps and platform engineer, 14+ years across Azure, Kubernetes, and CI/CD. Six of those years were client-facing
delivery lead roles for Citi Bank and a US health insurer, running distributed teams of up to 20 engineers. Strongest
hands-on in Terraform, Ansible, AKS, GitOps, and pipeline security. Built two platforms from scratch in 2026 and
published both on GitHub (an Azure Landing Zone and an AKS internal developer platform), and moved Claude Code and MCP
into daily automation work.

CORE SKILLS
Platform & GitOps: Kubernetes / AKS, Helm, ArgoCD (GitOps), internal developer platform, golden-path self-service, subscription vending
Cloud & IaC: Azure (Landing Zone, AKS, PostgreSQL Flex, Key Vault, VNet, OIDC, Migration), AWS, GCP, Terraform, Ansible, OpenStack
DevSecOps & Policy: OPA / Gatekeeper (policy-as-code), External Secrets, SonarQube, Checkmarx, JFrog Artifactory / Xray, SAST / SCA
Observability & Delivery Metrics: Master DevOps Dashboard (MTTR, deployment trends), scheduled drift detection, in-pipeline Kubernetes cost signals
CI/CD: Azure DevOps, Jenkins, Harness, Tekton, TeamCity, GitHub Actions, uDeploy, RLM, Copado
Containers: Docker, Kubernetes, Helm, AKS, EKS, GKE
Scripting & SCM: Python, Bash, PowerShell, YAML | Azure Repos, GitHub, Bitbucket, Git
Databases: PostgreSQL, Azure PostgreSQL Flexible Server, SQL Server (OLTP / OLAP), MySQL
AI & Productivity: Claude Code + MCP, GitHub Copilot, Perplexity AI
ITSM & Agile: ServiceNow, JIRA, Confluence, Remedy, HPSM, SAFe, Scrum

EXPERIENCE
Career Break - Independent Platform Engineering & AI-Assisted DevOps (Jan 2026 - Jul 2026, Hyderabad, India)
Planned break for family reasons, now resolved. Built two platforms end to end and published both on GitHub.
- Azure Landing Zone in Terraform as reusable modules: management-group hierarchy, Azure Policy governance, hub-and-spoke networking, subscription vending.
- Internal developer platform on AKS: ArgoCD for GitOps, OPA Gatekeeper for admission policy, External Secrets pulling from Key Vault over workload identity. A developer commits one YAML file and gets a namespace, pipeline, TLS, and secrets without raising a ticket.
- Uses Claude Code and MCP daily for Terraform module authoring, Helm scaffolding, and first-pass incident analysis.
- FinOps in practice: Kubernetes cost signals run inside the pipelines rather than a monthly spreadsheet.

Senior IT Specialist - DevOps / Platform, DSV Global Transport & Logistics (Jan 2024 - Dec 2025)
Azure, Terraform, Ansible, Azure DevOps, Python, Key Vault, PostgreSQL Flexible Server
- Reusable Terraform modules and Azure DevOps YAML pipelines provisioning PostgreSQL Flexible Server across 5 environments (DEV, QA, TST, PPR, PRD), covering new-instance, update, decommission, restore, and multi-instance flows.
- Moved pipelines to OIDC passwordless authentication, removing stored credentials and enforcing least-privilege access across Azure subscriptions and storage accounts.
- Built a Master DevOps Dashboard pulling MTTR and deployment-trend metrics from Azure DevOps, GitHub, JFrog, and SonarQube into one leadership view.
- Codified subscription-level network segmentation, private endpoints, and policy-driven resource placement across OLZ and NLZ zones.
- Ansible playbooks for PostgreSQL configuration, admin and user management, and secret retrieval from Passwordstate and Azure Key Vault.
- Multi-stage workflows (Plan, Apply, Post-Restore, Post-Deployment) with manual approvals, scheduled drift detection, and conditional destroy or restore logic.

Sr DevOps Consultant & Team Lead, Infosys Limited (Jul 2023 - Dec 2023) - Client: Citi Bank
Jenkins, RLM, SonarQube, Checkmarx, Bitbucket, TeamCity, uDeploy | 7-region rollout
- Single point of contact for Citi's CI/CD delivery across 7 regions. Led 18-20 engineers as Scrum Master.
- Ran Jenkins and RLM across all 7 regions: setup, configuration, patching, and vulnerability remediation.

Sr DevOps Consultant & Team Lead, Infosys Limited (Jan 2021 - Jun 2023) - Client: Citi Bank
Jenkins, RLM, uDeploy, TeamCity, Bitbucket, Harness, Tekton, Helm
- Designed and delivered the CI/CD system for Citi's next-generation data-analytics platform across 7 global regions.
- Harness CD pipelines with Helm packaging for Kubernetes, and Tekton pipelines for cloud-native CI.
- Owned the full delivery lifecycle for an 18-20 person distributed team: scope and sprint planning, SLA and risk management, escalations, onboarding, knowledge transfer.

Azure DevOps Implementation Engineer & Team Lead, Tata Consultancy Services (Jun 2019 - Jan 2021) - Client: US Health Insurance Organization
Azure DevOps, MSBI, DataStage, .NET | On-prem & Azure
- Client-facing delivery lead and single POC, running a 9-12 person onshore and offshore team across time zones.
- Installed, configured, and administered Azure DevOps on-prem: roles and rights, repositories, pipelines, deployments, release management.
- Built CI/CD for .NET, DataStage, and MSBI across on-prem and Azure, and migrated workloads into Azure under enterprise landing-zone standards.

Database Administrator & BI Developer, Tata Consultancy Services (Mar 2017 - Jun 2019)
- Administered 90+ SQL Server production instances (2005-2016): backup, recovery, maintenance planning, 24x7 production support.
- High availability with Log Shipping, Database Mirroring, Replication, and Clustering; set up Azure DevOps on-prem for CI/CD.

Database Administrator, Wifin Technologies India Pvt Ltd (May 2012 - Mar 2017)
- Managed 40+ SQL Server instances (2000-2016). Led upgrades and migrations from SQL Server 2000/2005 to 2008 and 2008 R2.

CERTIFICATIONS
Microsoft Certified DevOps Professional (AZ-400); AWS Cloud Practitioner; FinOps Certified Practitioner (Linux Foundation);
Copado Certified Salesforce DevOps Administrator / Developer / Professional; Microsoft Certified in SQL Querying & Tuning

AWARDS
Technical Excellence Award (Infosys); Business Ninja Award (Infosys); Insta Award (TCS)
"""
##<
'''
Note: If left empty as "", the tool will not answer the question. However, note that some companies make it compulsory to be answered. Use \n to add line breaks.
''' 

# Name of your most recent employer
recent_employer = "DSV Global Transport & Logistics" # "", "Lala Company", "Google", "Snowflake", "Databricks"

# Example question: "On a scale of 1-10 how much experience do you have building web or mobile applications? 1 being very little or only in school, 10 being that you have built and launched applications to real users"
confidence_level = "9"             # Any number between "1" to "10" including 1 and 10, put it in quotes ""
##



# >>>>>>>>>>> RELATED SETTINGS <<<<<<<<<<<

## Allow Manual Inputs
# Should the tool pause before every submit application during easy apply to let you check the information?
pause_before_submit = True         # True or False, Note: True or False are case-sensitive
'''
Note: Will be treated as False if `run_in_background = True`
'''

# Should the tool pause if it needs help in answering questions during easy apply?
# Note: If set as False will answer randomly...
pause_at_failed_question = True    # True or False, Note: True or False are case-sensitive
'''
Note: Will be treated as False if `run_in_background = True`
'''
##

# Do you want to overwrite previous answers?
overwrite_previous_answers = False # True or False, Note: True or False are case-sensitive







############################################################################################################
'''
THANK YOU for using my tool 😊! Wishing you the best in your job hunt 🙌🏻!

Sharing is caring! If you found this tool helpful, please share it with your peers 🥺. Your support keeps this project alive.

Support my work on <PATREON_LINK>. Together, we can help more job seekers.

As an independent developer, I pour my heart and soul into creating tools like this, driven by the genuine desire to make a positive impact.

Your support, whether through donations big or small or simply spreading the word, means the world to me and helps keep this project alive and thriving.

Gratefully yours 🙏🏻,
Sai Vignesh Golla
'''
############################################################################################################