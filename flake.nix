{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    devenv.url = "github:cachix/devenv";
  };
  outputs =
    inputs@{ flake-parts, nixpkgs, ... }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      imports = [
        inputs.devenv.flakeModule
      ];
      systems = nixpkgs.lib.systems.flakeExposed;
      perSystem =
        { pkgs, ... }:
        let
          python = pkgs.python311;
          libraries = with pkgs; [
            stdenv.cc.cc
            libffi
            zlib
            libuv
          ];
          LIBRARY_PATH = if pkgs.stdenv.isDarwin then "DYLD_LIBRARY_PATH" else "LD_LIBRARY_PATH";
        in
        {
          devenv.shells.default = {
            packages = [
              python.pkgs.panel
            ];
            languages.python = {
              enable = true;
              package = python;
              uv = {
                enable = true;
                sync = {
                  enable = true;
                  allExtras = true;
                };
              };
            };
            env = {
              ${LIBRARY_PATH} = "${with pkgs; lib.makeLibraryPath libraries}";
              UV_PYTHON = "${python}/bin/python";
            };
          };
        };
    };
}
