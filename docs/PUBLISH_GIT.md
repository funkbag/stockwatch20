# Publish as a Git repository

The source package is repository-ready but intentionally does not include a `.git` directory.

## 1. Initialize locally

From the project directory:

```bash
git init
git branch -M main
git add .
git status
```

Before committing, verify `.env` and `data/state.json` are **not** listed under files to be committed.

Then:

```bash
git commit -m "Initial StockWatch 20 release"
```

If Git asks for identity:

```bash
git config --global user.name "Your Name"
git config --global user.email "your-email@example.com"
```

Then repeat the commit.

## 2. Create an empty remote repository

Create a new private or public repository on your Git hosting service. Do not initialize it with a README, `.gitignore`, or license because those are already present locally.

Copy the repository URL, for example:

```text
git@github.com:USERNAME/stockwatch20.git
```

or:

```text
https://github.com/USERNAME/stockwatch20.git
```

The same Git commands work with Gitea, GitLab, or other standard Git remotes.

## 3. Add the remote and push

```bash
git remote add origin <REMOTE-URL>
git push -u origin main
```

Verify:

```bash
git remote -v
git status
```

## 4. Connect metrix01 to the repository

For a fresh install, follow `DEPLOYMENT_METRIX01.md`.

For the existing manually deployed `/opt/stockwatch`, first make a backup and preserve `.env` and `data/`. Then convert the directory to the Git-managed version using the migration instructions in `DEPLOYMENT_METRIX01.md`.

## Normal update workflow after that

Development machine:

```bash
git add .
git commit -m "Describe change"
git push
```

metrix01:

```bash
cd /opt/stockwatch
git pull --ff-only
docker compose up -d --build
```
