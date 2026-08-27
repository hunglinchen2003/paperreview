import subprocess

def run(cmd):
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    out, err = p.communicate()
    out_str = out.decode('utf-8', errors='replace').strip()
    err_str = err.decode('utf-8', errors='replace').strip()
    print(f">> {cmd}")
    if out_str:
        print(f"STDOUT: {out_str}")
    if err_str:
        print(f"STDERR: {err_str}")
    print(f"CODE: {p.returncode}\n")
    return p.returncode

run('git config user.name "hunglinchen2003"')
run('git config user.email "hunglinchen2003@gmail.com"')
run('git remote remove origin')
run('git remote add origin https://github.com/hunglinchen2003/paperreview.git')
run('git branch -M main')
run('git add .')
run('git commit -m "Initial commit for Galectin Literature Review and GitHub Pages"')
run('git push -u origin main')
