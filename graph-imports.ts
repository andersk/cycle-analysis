import * as fs from "fs";
import * as fsPath from "path";

import { namedTypes as n } from "ast-types";
import type { NodePath } from "ast-types/lib/node-path";
import type { Scope } from "ast-types/lib/scope";
import * as recast from "recast";
import * as babelParser from "recast/parsers/babel";
import * as tsParser from "recast/parsers/typescript";

const files = process.argv.slice(2);
const fileSet = new Set(files);

for (const file of files) {
  console.warn("# parsing", file);
  const ast = recast.parse(fs.readFileSync(file, "utf8"), {
    parser: fsPath.extname(file) === ".ts" ? tsParser : babelParser,
  });
  const sources = new Map<Scope, Map<string, string>>();
  const counts = new Map<string, number>();

  const visitImport = (
    path: NodePath<n.ExportNamedDeclaration> | NodePath<n.ImportDeclaration>,
  ) => {
    if (
      n.StringLiteral.check(path.node.source) &&
      (path.node.source.value.startsWith("./") ||
        path.node.source.value.startsWith("../")) &&
      path.node.specifiers !== undefined
    ) {
      let source = fsPath.relative(
        ".",
        fsPath.join(fsPath.dirname(file), path.node.source.value),
      );
      if (fileSet.has(`${source}.ts`)) {
        source = `${source}.ts`;
      } else if (fileSet.has(`${source}.js`)) {
        source = `${source}.js`;
      }
      if (!counts.has(source)) {
        counts.set(source, 0);
      }
      for (const specifier of path.node.specifiers) {
        if (n.Identifier.check(specifier.local)) {
          const scope = path.scope.lookup(specifier.local.name);
          if (!sources.has(scope)) {
            sources.set(scope, new Map<string, string>());
          }
          sources.get(scope)!.set(specifier.local.name, source);
        }
      }
    }
  };

  recast.visit(ast, {
    visitClassMethod(path): false | void {
      if (path.node.computed) {
        this.traverse(path);
      } else {
        this.visit(path.get("params"));
        this.visit(path.get("body"));
        return false;
      }
    },
    visitClassProperty(path): false | void {
      if (path.node.computed) {
        this.traverse(path);
      } else {
        this.visit(path.get("value"));
        return false;
      }
    },
    visitExportNamedDeclaration(path) {
      visitImport(path);
      this.visit(path.get("declaration"));
    },
    visitImportDeclaration(path) {
      visitImport(path);
      return false;
    },
    visitIdentifier(path) {
      const scope = path.scope.lookup(path.node.name);
      const source = sources.get(scope)?.get(path.node.name);
      if (source !== undefined) {
        counts.set(source, counts.get(source)! + 1);
      }
      return false;
    },
    visitMemberExpression(path): false | void {
      if (path.node.computed) {
        this.traverse(path);
      } else {
        this.visit(path.get("object"));
        return false;
      }
    },
    visitObjectMethod(path): false | void {
      if (path.node.computed) {
        this.traverse(path);
      } else {
        this.visit(path.get("body"));
        return false;
      }
    },
    visitObjectProperty(path): false | void {
      if (path.node.computed) {
        this.traverse(path);
      } else {
        this.visit(path.get("value"));
        return false;
      }
    },
    visitProperty(path): false | void {
      if (path.node.computed) {
        this.traverse(path);
      } else {
        this.visit(path.get("value"));
        return false;
      }
    },
  });
  for (const [source, count] of counts.entries()) {
    console.log(file, source, count);
  }
}
