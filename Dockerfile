CMD ["gunicorn", "--bind", "0.0.0.0:4000", "--workers", "2", "--timeout", "120", "app:app"]
```

Also add `package.json` to your `.dockerignore` so Docker doesn't get confused:
```
package.json
package-lock.json
node_modules/
venv/
__pycache__/
android/
www/