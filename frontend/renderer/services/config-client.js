// Cliente HTTP do endpoint de configuração do backend.

import { BACKEND_HTTP } from "./config.js";

export async function fetchConfig() {
  const res = await fetch(`${BACKEND_HTTP}/config`);
  return res.json();
}
