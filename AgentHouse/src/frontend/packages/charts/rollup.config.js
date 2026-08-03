import typescript from "@rollup/plugin-typescript";
import resolve from "@rollup/plugin-node-resolve";
import commonjs from "@rollup/plugin-commonjs";
import postcss from "rollup-plugin-postcss";
import autoprefixer from "autoprefixer";
import tailwindcss from "tailwindcss";
import path from "path";

const isDevelopment = process.env.NODE_ENV === "development";

export default {
  input: "src/index.ts",
  output: [
    { file: "dist/index.cjs.js", format: "cjs", sourcemap: isDevelopment },
    { file: "dist/index.esm.js", format: "esm", sourcemap: isDevelopment },
  ],
  plugins: [
    resolve(),
    commonjs(),
    typescript({
      tsconfig: "./tsconfig.json",
      sourceMap: isDevelopment,
      inlineSources: isDevelopment,
    }),
    postcss({
      extensions: [".css"],
      extract: path.resolve("dist/styles.css"),
      plugins: [tailwindcss, autoprefixer],
    }),
  ],
  external: ["react", "react-dom"],
};
