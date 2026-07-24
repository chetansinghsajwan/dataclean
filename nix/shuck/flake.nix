{
  description = "shuck - a fast shell script linter, formatter, and language server";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";  # or aarch64-darwin, aarch64-linux, x86_64-darwin
      pkgs = import nixpkgs { inherit system; };
    in {
      packages.${system}.shuck = pkgs.rustPlatform.buildRustPackage rec {
        pname = "shuck";
        version = "0.0.45";

        src = pkgs.fetchFromGitHub {
          owner = "ewhauser";
          repo = "shuck";
          rev = "v${version}";
          hash = "sha256-xh5f9lnI3eICvcVXjeDZ3A1LrR2/lK4W9KddHIh1IvU=";
        };

        cargoHash = "sha256-liKoeJBB3GeSpj4T/ty++MmUoO0qEzbNPZb07UEzrfU=";

        # shuck is a Cargo workspace (multiple crates: shuck-cli, shuck-parser, etc.)
        # buildRustPackage builds all workspace binaries by default; if you only
        # want the `shuck` binary from shuck-cli, uncomment and adjust:
        # cargoBuildFlags = [ "-p" "shuck-cli" ];

        # Skip tests — shuck's suite downloads large corpora of real-world shell
        # scripts over the network for conformance testing, which the Nix build
        # sandbox blocks. It also may hit the same sandboxed-git issue seen with
        # nbwipers, since it shells out for some diagnostics/tests.
        doCheck = false;

        meta = with pkgs.lib; {
          description = "A fast shell script linter, formatter, and language server, written in Rust";
          homepage = "https://github.com/ewhauser/shuck";
          license = licenses.mit;
          mainProgram = "shuck";
        };
      };
    };
}
