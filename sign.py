#!/usr/bin/env python3
"""Signed release archive of the app for the Nextcloud app store.

  sign.py [--key KEY] [--cert CERT] [--image IMAGE] [OUTDIR]

  KEY, CERT  default ~/.nextcloud/certificates/untrash.{key,crt}
             (the certificate Nextcloud issued for the app id "untrash")
  IMAGE      default nextcloud:35-apache
  OUTDIR     default build

writes into OUTDIR
  untrash-<version>.tar.gz      the app with appinfo/signature.json (code signing)
  untrash-<version>.tar.gz.sig  base64 SHA-512 signature of that archive: the
                                "signature" field of an app store release upload
  untrash-cloud-wg-<version>.tar.gz, SHA256SUMS   as package.py

appinfo/signature.json is made by Nextcloud itself (occ integrity:sign-app) in
a throwaway container ("sudo -n docker"); the key is copied in only for that
and the container is removed.  The archive is not byte-reproducible: the
signature in signature.json is randomized (RSA-PSS).
"""
import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import package  # noqa: E402

CERTS = os.path.expanduser("~/.nextcloud/certificates")


def docker(*a, check=True):
    r = subprocess.run(["sudo", "-n", "docker"] + list(a), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if check and r.returncode:
        sys.exit("docker %s: %s" % (" ".join(a[:2]), r.stdout[-1500:]))
    return r.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", default=os.path.join(CERTS, "untrash.key"))
    ap.add_argument("--cert", default=os.path.join(CERTS, "untrash.crt"))
    ap.add_argument("--image", default="nextcloud:35-apache")
    ap.add_argument("outdir", nargs="?", default=os.path.join(HERE, "build"))
    a = ap.parse_args()
    for f in (a.key, a.cert):
        if not os.path.isfile(f):
            sys.exit("missing " + f)
    cn = subprocess.run(["openssl", "x509", "-in", a.cert, "-noout", "-subject", "-nameopt", "multiline"],
                        capture_output=True, text=True, check=True).stdout
    if "commonName" not in cn or "= untrash" not in cn:
        sys.exit("the certificate is not for the app id untrash:\n" + cn)
    ver, epoch = package.version(), package.source_epoch()
    os.makedirs(a.outdir, exist_ok=True)
    name = "ut-sign-%d" % os.getpid()
    with tempfile.TemporaryDirectory() as w:
        src = os.path.join(w, "untrash")
        for path, arc in package.app_files():
            dst = os.path.join(w, arc)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(path, dst)
        docker("run", "-d", "--name", name, "-e", "SQLITE_DATABASE=nc", "-e", "NEXTCLOUD_ADMIN_USER=signer",
               "-e", "NEXTCLOUD_ADMIN_PASSWORD=throwaway-%d" % os.getpid(), a.image)
        try:
            for _ in range(120):
                if "installed: true" in docker("exec", "-u", "www-data", name, "php", "occ", "status", check=False):
                    break
                time.sleep(2)
            else:
                sys.exit("the signing container did not finish installing")
            docker("exec", name, "mkdir", "-p", "/sign")
            docker("cp", src, name + ":/sign/untrash")
            docker("cp", a.key, name + ":/sign/app.key")
            docker("cp", a.cert, name + ":/sign/app.crt")
            docker("exec", name, "chown", "-R", "www-data:", "/sign")
            out = docker("exec", "-u", "www-data", name, "php", "occ", "integrity:sign-app",
                         "--privateKey=/sign/app.key", "--certificate=/sign/app.crt", "--path=/sign/untrash")
            if "Successfully signed" not in out:
                sys.exit("sign-app: " + out)
            docker("cp", name + ":/sign/untrash/appinfo/signature.json", os.path.join(src, "appinfo", "signature.json"))
        finally:
            docker("rm", "-f", name, check=False)
        entries = [(os.path.join(w, arc), arc) for _, arc in package.app_files()]
        entries.append((os.path.join(src, "appinfo", "signature.json"), "untrash/appinfo/signature.json"))
        app = os.path.join(a.outdir, "untrash-%s.tar.gz" % ver)
        package.write_tgz(app, entries, epoch)
    helper = os.path.join(a.outdir, "untrash-cloud-wg-%s.tar.gz" % ver)
    package.write_tgz(helper, [(os.path.join(package.SERVER, f), "untrash-cloud-wg/" + f) for f in package.HELPER], epoch)
    sig = subprocess.run(["openssl", "dgst", "-sha512", "-sign", a.key, app], capture_output=True, check=True).stdout
    b64 = subprocess.run(["openssl", "base64", "-A"], input=sig, capture_output=True, check=True).stdout.decode()
    with open(app + ".sig", "w") as fh:
        fh.write(b64 + "\n")
    with open(os.path.join(a.outdir, "SHA256SUMS"), "w") as fh:
        for p in (app, helper):
            with open(p, "rb") as f:
                fh.write("%s  %s\n" % (hashlib.sha256(f.read()).hexdigest(), os.path.basename(p)))
    print(app)
    print(app + ".sig")
    print(helper)


if __name__ == "__main__":
    main()
