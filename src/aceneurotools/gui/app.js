"use strict";
fetch("/api/health").then(response => { if (!response.ok) throw new Error(); return response.json(); }).then(() => { document.getElementById("status").textContent = "Your local application is ready."; }).catch(() => { document.getElementById("status").textContent = "Unable to connect. Restart ACE-NeuroTools."; });
