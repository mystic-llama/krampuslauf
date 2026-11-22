# Publish Krampuslauf on GitHub

Prepared for **Mystic Llama**, version **1.8.0-beta.4**. These steps use GitHub Desktop on Windows and your repository at <https://github.com/mystic-llama/krampuslauf>.

The package has been prepared locally. Nothing has been committed, pushed or published on your behalf. The existing repository contents and its older commit history were not available for this source review.

## What the buttons mean

- **Clone:** download a working copy of your GitHub repository.
- **Commit:** record a set of changes on your computer.
- **Push origin:** upload those commits to GitHub.
- **Release:** publish a named version with notes and downloadable ZIP files.

Committing locally does not publish the changes until you push them.

## 1. Prepare the files and your commit identity

1. Extract `Krampuslauf_1.8.0-beta.4_Full_Source.zip` into a fresh folder. Use this complete source package as the publishing copy.
2. Keep `%LOCALAPPDATA%\Krampuslauf` and the actual Razor installation/data folders outside your repository. They are private runtime data, not source code.
3. The included `LICENSE` is the MIT license with **Copyright (c) 2026 Mystic Llama**, as requested. MIT permits reuse, modification and commercial redistribution while requiring retention of the copyright and license notices. Third-party dependencies keep their own terms. Preserve any existing third-party notices.
4. In GitHub's account **Settings > Emails**, enable **Keep my email addresses private** if you want privacy, and copy the exact GitHub-provided `noreply` address. You can also enable the setting that blocks pushes exposing your private email.
5. In GitHub Desktop on Windows, open **File > Options > Git**. Set the commit name you want public, such as **Mystic Llama**, and use that exact `noreply` address. Save. This affects future commits; it does not rewrite old ones.

## 2. Clone Krampuslauf

1. Install [GitHub Desktop](https://desktop.github.com/) and sign in to the account that owns `mystic-llama/krampuslauf`.
2. Choose **File > Clone repository > URL**.
3. Enter `https://github.com/mystic-llama/krampuslauf.git`.
4. Select a normal local development folder and click **Clone**. Do not choose your app-data folder or Razor installation.
5. If you already have a clean local clone, select it instead. Use **Fetch origin**, then **Pull origin** if Desktop offers updates, before copying the new files. Preserve any uncommitted work first.

If GitHub says the repository cannot be found, verify the URL and signed-in account. A private repository requires access. Do not create a second repository simply to bypass an access problem.

## 3. Put the source in the right place

1. In Desktop, select `krampuslauf`, choose the branch you want to release, then use **Repository > Show in Explorer**.
2. The repository root is the application. Update the files in that folder rather than nesting another Krampuslauf directory inside it.
3. Copy the **contents** of the extracted source folder into the repository root. You should see `Krampuslauf.py`, `README.md`, `CONFIGURATION.md`, `LICENSE`, `.gitignore`, `assets`, `docs` and `tests` together.
4. If an existing `.gitignore` has your own rules, merge the new exclusions with those rules. Leave unrelated files in the clone untouched.
5. Keep source files extracted in the repository. Attach downloadable ZIPs under Releases later.

The application-level `.gitignore` applies within its folder. It excludes private settings/history, markers, Razor files/backups, environment files, private keys, build output and release archives. It keeps the source, tests, artwork, license and documentation eligible for commit. It does not inspect ZIP contents or remove previously tracked files.

## 4. Review and commit

1. Return to GitHub Desktop and open **Changes**.
2. Read the list before checking files for this commit. Include the Krampuslauf source and its `.gitignore`, `LICENSE`, artwork, tests and guides. Leave unrelated changes out.
3. Look for anything unexpected: real account/settings JSON, activity logs, calibration screenshots, a `Profiles` or `Backup` folder, secrets, a virtual environment, or compiled build output. None belongs in this source commit.
4. If a private file is already tracked, a new ignore rule will not hide it. Stop and remove it from tracking before pushing. If a real password/token was already exposed, revoke or rotate it; deleting the current file alone does not remove it from older commits.
5. In **Summary**, enter:

   ```text
   Prepare Krampuslauf 1.8.0-beta.4 public beta
   ```

6. An optional description is:

   ```text
   Add saved transfer-slot reservation for both creation modes while retaining
   existing-character gift eligibility and recovery safeguards. Include the
   MIT license, profile-recovery hardening, artwork and release guides.
   ```

7. Click **Commit to [your branch]**. Review that commit in **History** if you want to inspect it once more.
8. Click **Push origin** to upload it. If the branch requires a pull request, follow the repository's review process before releasing it.
9. Use **Repository > View on GitHub** and confirm the intended files and commit are present.

## 5. If you want to distribute a Windows app

This package contains source. A Windows executable has not been built or live-tested in this review environment.

1. Use a clean source folder and Python 3.12 or newer on Windows. Run `Build_Windows_EXE.bat`.
2. The batch file installs dependencies and PyInstaller, then creates `dist\Krampuslauf\Krampuslauf.exe`.
3. Launch the EXE from that distribution folder. Confirm all three main tabs, the 350 × 350 Setup logo, the Help artwork, readable notices and the included configuration guide.
4. Back up real app data privately, then validate preparation/restoration of Razor profiles, bridge connection/logout and one existing-character gift run. Test Pause/Resume/Stop before any real character creation. Check Windows scaling at the settings you intend to support.
5. Keep `_internal`, `assets`, `docs`, `krampuslauf_bridge.py`, `README.md`, `CONFIGURATION.md`, `CHANGELOG.md`, `VERSION.txt` and `LICENSE` with the EXE. Preserve bundled dependency license notices; the project's MIT license does not replace them.
6. Record the dependency versions used for the actual Windows build and check them for known vulnerabilities. The requirements currently permit version ranges, so a later build may install different versions. Do not describe the dependency set as audited unless you checked the resolved Windows environment.
7. ZIP the **entire** `dist\Krampuslauf` folder, for example as `Krampuslauf_1.8.0-beta.4_Windows.zip`. Review its contents before uploading. Do not add your app-data folder, logs, calibration captures or Razor profiles.

A source patch cannot update an existing EXE. Rebuild from the new source. Never ask users to disable antivirus merely to run a beta.

## 6. Create the GitHub beta release

1. Open the repository on GitHub, then **Releases > Draft a new release**.
2. Under **Choose a tag**, create **`v1.8.0-beta.4`**. If that exact tag already exists for different code, use the next unused version instead of moving the old tag.
3. Choose the branch or commit containing the source you just pushed.
4. Set the title to **Krampuslauf 1.8.0-beta.4**.
5. Paste the contents of [`RELEASE_NOTES.md`](RELEASE_NOTES.md) into the description. It accurately describes a source beta. If you have subsequently built and tested a Windows ZIP, update its download paragraph to identify that attachment and summarize the Windows validation you actually completed.
6. Attach the full source ZIP and `CONFIGURATION.md`. Attach the Windows ZIP only after completing the build/test steps above. GitHub also generates source archives for the repository tag; those contain this repository.
7. Check **This is a pre-release**.
8. Use **Save draft** while reviewing. When the version, files and notes are ready, click **Publish release**.
9. Open the public release page and verify its download links and configuration instructions.

## Official references

- [Clone with GitHub Desktop](https://docs.github.com/en/desktop/adding-and-cloning-repositories/cloning-and-forking-repositories-from-github-desktop)
- [Commit, review and push](https://docs.github.com/en/desktop/making-changes-in-a-branch/committing-and-reviewing-changes-to-your-project-in-github-desktop)
- [Configure your Desktop commit identity](https://docs.github.com/en/desktop/configuring-and-customizing-github-desktop/configuring-git-for-github-desktop)
- [Commit email privacy](https://docs.github.com/en/account-and-profile/how-tos/email-preferences/setting-your-commit-email-address)
- [Ignoring files](https://docs.github.com/en/get-started/getting-started-with-git/ignoring-files)
- [Managing releases](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)
- [MIT license](https://choosealicense.com/licenses/mit/)
