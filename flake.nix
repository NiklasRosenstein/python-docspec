{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };
  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let pkgs = import nixpkgs { inherit system; };
      in {
        packages.lint = pkgs.writeShellScriptBin "lint" ''
          set -e
          ${pkgs.ruff}/bin/ruff check .
          ( cd docspec/ && ${pkgs.uv}/bin/uv run mypy . --check-untyped-defs )
          ( cd docspec-python/ && ${pkgs.uv}/bin/uv run mypy . --check-untyped-defs )
        '';

        packages.test = pkgs.writeShellScriptBin "test" ''
          set -e
          ( cd docspec/ && ${pkgs.uv}/bin/uv run pytest . )
          ( cd docspec-python/ && ${pkgs.uv}/bin/uv run pytest . )
        '';

        packages.docs = let
          slap = pkgs.writeShellScriptBin "slap" ''
            ${pkgs.uv}/bin/uv tool run --from slap-cli slap -- "$@"
          '';
        in pkgs.writeShellScriptBin "docs" ''
          set -e
          export PATH="${slap}/bin:$PATH"
          ( cd docs/ && ${pkgs.uv}/bin/uv run novella --base-url docspec/ "$@" )
        '';

        formatter = pkgs.writeShellScriptBin "ruff" ''
          set -e
          ${pkgs.nixfmt-classic}/bin/nixfmt .
          ${pkgs.ruff}/bin/ruff format .
        '';

        devShells.default = pkgs.mkShell { nativeBuildInputs = [ pkgs.uv ]; };
      });
}
