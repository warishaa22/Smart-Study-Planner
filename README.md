FocusFlow AI — Smart Study Planner

FocusFlow AI helps university students organize assignments, exam preparation, revision, projects, and personal goals. It builds a priority-based daily plan, visualizes task progress, and uses Gemini Flash to provide study coaching and suggestions for recovering when work falls behind.
Features
- Add tasks with a subject, task type, deadline, priority, and estimated hours remaining.
- Mark tasks complete or delete tasks.
- Identify overdue work and track overall completion.
- Build a deterministic local plan that respects the available study-hour limit.
- Ask Gemini Flash for an ordered study plan, break suggestions, and recovery advice.
- Include weekly class commitments and personal goals as context for AI advice.
- View progress charts by completion status and subject.
- Export tasks to CSV.
- Continue to use the local planner when no Gemini API key is configured.
Project files
focusflow-ai/
├── app.py
├── requirements.txt
└── README.md
Requirements
- Python 3.10 or newer (Python 3.11 or 3.12 recommended)
- A Google Gemini API key from Google AI Studio
- Internet access for Gemini-powered advice
Run locally
1. Download or clone this repository and open a terminal in the project folder.
2. Create and activate a virtual environment (recommended).
   Windows PowerShell:
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   macOS / Linux:
   python3 -m venv .venv
   source .venv/bin/activate
3. Install dependencies:
   python -m pip install -r requirements.txt
4. Configure your Gemini API key. Create a folder named .streamlit in the project root, then create .streamlit/secrets.toml with:
   GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
   GEMINI_MODEL = "gemini-flash-latest"
   The model name can be changed in the app sidebar if your API account uses another supported Gemini Flash model ID. You can also set GEMINI_API_KEY and GEMINI_MODEL as environment variables.
5. Start the app:
   streamlit run app.py
6. Open the local URL printed in the terminal (usually http://localhost:8501).
Using the app
1. Set the number of study hours available today in the sidebar.
2. Optionally enter class times / fixed commitments and personal goals.
3. Add assignments, exam preparation, revision, projects, and personal goals.
4. Mark tasks complete as you finish them.
5. Select Generate / replan my day to create a fresh schedule and request Gemini coaching.
6. Download your tasks as CSV for a backup.
Push the project to GitHub
1. Create a repository
- Sign in at GitHub.
- Click New repository.
- Name it focusflow-ai.
- Choose Public if you want to show it in your portfolio, or Private if you prefer.
- Create the repository. If you are pushing an existing local folder, it is simplest to leave README initialization unchecked to avoid merge conflicts.
2. Protect your API key
Before committing, create a .gitignore file in your project folder with:
.streamlit/secrets.toml
.venv/
__pycache__/
*.py[cod]
.env
Never commit or share your Gemini API key. If a key is accidentally published, revoke it in Google AI Studio and create a new one.
3. Push from the terminal
Install Git if needed, then run these commands from the project folder. Replace the URL with your own repository URL:
git init
git add app.py requirements.txt README.md .gitignore
git commit -m "Build FocusFlow AI study planner"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/focusflow-ai.git
git push -u origin main
If Git asks you to authenticate, follow GitHub's current sign-in or credential-manager instructions. Do not use your Gemini key as a GitHub password.

For later updates:
git add .
git commit -m "Improve FocusFlow AI"
git push
Deploy on Streamlit Community Cloud
1. Push the repository to GitHub.
2. Open Streamlit Community Cloud and sign in with GitHub.
3. Select Create app.
4. Select your focusflow-ai repository, the main branch, and app.py as the main file.
5. Open Advanced settings / Secrets and add:
   GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
   GEMINI_MODEL = "gemini-flash-latest"
6. Deploy the app and wait for the build to finish.
7. Open the generated *.streamlit.app URL and test task creation and AI planning.
If deployment fails, open the app's logs in Community Cloud. Confirm that requirements.txt is in the repository root and that the secrets are configured in the app settings, not committed to GitHub.
Testing checklist
- [ ] The app starts with streamlit run app.py.
- [ ] A task can be added with a title and subject.
- [ ] Empty task title or subject is rejected.
- [ ] Completion metrics and charts update after task changes.
- [ ] The local plan does not schedule more hours than the daily limit.
- [ ] Completed tasks are excluded from the plan.
- [ ] Overdue tasks receive high scheduling urgency.
- [ ] The app still shows a local plan if no Gemini key is configured.
- [ ] With a valid key and model, Gemini returns coaching advice.
- [ ] CSV export downloads the task list.
- [ ] The deployed app works after its secrets are configured.
Important limitations
- This starter version keeps tasks in Streamlit session state. Tasks are not a permanent database and may be lost when the session resets or the app restarts. Export a CSV for backup. SQLite or a hosted database can be added as a future enhancement.
- Class commitments are passed to Gemini as context, but the local scheduler does not yet block out exact class time slots. Verify AI-generated schedules against your real calendar.
- Gemini output is generated advice and may be imperfect. Check deadlines, time estimates, and recommendations before following the plan.
- API availability, quotas, and model IDs depend on your Google AI Studio/API configuration.
Tech stack
- Streamlit — interface
- Google Gen AI Python SDK — Gemini API
- Pandas — task tables and analytics
- Plotly — charts
Future improvements
- Persistent SQLite / cloud database storage
- Weekly calendar with class-time blocking
- Automatic rescheduling across multiple days
- Study timers and session history
- Authentication and separate user accounts
- Calendar integration and reminders
License
Choose and add a license before redistributing this project publicly. For a personal learning project, an MIT license is a common option.
