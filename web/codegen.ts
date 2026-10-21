import type { CodegenConfig } from "@graphql-codegen/cli";

const config: CodegenConfig = {
  schema: "schema.graphql",
  documents: ["src/**/*.{ts,tsx}", "!src/gql/**/*"],
  ignoreNoDocuments: false,
  errorsOnly: true,
  generates: {
    "src/gql/": {
      preset: "client",
      config: {
        scalars: {
          UUID: "string",
          Date: "string",
          DateTime: "string",
          MinorUnits: "number",
        },
        enumsAsTypes: true,
        useTypeImports: true,
      },
    },
  },
};

export default config;
