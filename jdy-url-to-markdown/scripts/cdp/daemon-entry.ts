import { CDPDaemon } from "./daemon";

const daemon = new CDPDaemon();
daemon.start().catch((e) => {
  console.error(`[daemon] Fatal: ${e.message}`);
  process.exit(1);
});
