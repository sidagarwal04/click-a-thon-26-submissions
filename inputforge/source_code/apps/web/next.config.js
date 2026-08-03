import { withEve } from "eve/next";
import { withWorkflow } from "workflow/next";

/** @type {import('next').NextConfig} */
const nextConfig = {
  allowedDevOrigins: ["127.0.0.1"],
};

export default withWorkflow(
  withEve(nextConfig, { eveRoot: "../sentinel-agent" }),
);
