# Face Identification & Blockchain Verification Pipeline

**HH Goa 2026 — Shortlisting Task 3**

## What it does
End-to-end pipeline: face scan → live reverse-image search to find a matching web/social post →
blockchain fingerprinting & re-verification of that discovered data.

1. **Face identification** — detects and encodes the face in an input image using `face_recognition`
   (dlib 128-d embeddings), with an automatic OpenCV Haar Cascade fallback if `face_recognition`
   fails to install.
2. **Web/social search** — uploads the image anonymously (via catbox.moe) to get a public URL, then
   runs a genuine live reverse-image search using SerpApi's `google_reverse_image` engine. No
   hardcoded/pre-picked results.
3. **Blockchain verification** — hashes the image, the face encoding, and the matched post into a
   single fingerprint, writes it to a local SHA-256 hash-linked blockchain (default), or optionally
   anchors it as a real transaction on the Ethereum **Sepolia testnet**. Re-verifies the fingerprint
   against the on-chain record to prove tamper-evidence.

## How to run
1. `pip install -r requirements.txt` (or just run the first cell of the notebook, which installs
   everything itself).
2. Open `face_blockchain_pipeline.ipynb` in Jupyter, VS Code, or Google Colab.
3. In the **CONFIG** cell, set:
   - `IMAGE_PATH` — path to a face photo (or use the optional upload widget cell).
   - `SERPAPI_KEY` — free key from https://serpapi.com/manage-api-key (or leave blank to be
     prompted securely at runtime).
   - `USE_REAL_BLOCKCHAIN` — leave `False` for the local simulated chain, or `True` + fill in
     `SEPOLIA_RPC_URL` and `WALLET_PRIVATE_KEY` to anchor on a real testnet.
4. Run all cells top to bottom.

## Blockchain used
- **Default:** local simulated SHA-256 hash-linked blockchain (own implementation in-notebook).
- **Optional:** Ethereum **Sepolia testnet**, via a zero-value self-transaction carrying the
  fingerprint hash in its `data` field (no smart contract deployment required). Verifiable on
  Sepolia Etherscan.

## Known limitations
- Reverse image search quality depends on the input photo already being indexed somewhere publicly
  online — it won't find matches for images that have never appeared on the web.
- SerpApi's free tier is rate-limited (250 searches/month).
- The OpenCV fallback encoding (used only if `face_recognition`/dlib fails to install) is a simple
  pixel-based vector, not a true face-recognition embedding — it keeps the pipeline running but is
  not suitable for real face matching.
- The image is briefly hosted on a public anonymous file host (catbox.moe) to obtain a URL for the
  search API; only use this with images you have the right to share.
