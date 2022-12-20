{
  description = "The Artemis moon phase server.";

  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-22.11";

  outputs =
    { self
    , nixpkgs
    , flake-utils
    }@args:
    let
      systemOutputs = flake-utils.lib.eachDefaultSystem (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};

          python = pkgs.python3.withPackages (p: with p; [
            skyfield
          ]);
        in
        rec {
          apps.default = apps.artemis;
          apps.artemis = flake-utils.lib.mkApp {
            drv = packages.artemis;
          };

          devShells.default = devShells.artemis;
          devShells.artemis = pkgs.mkShell {
            name = "artemis-shell";

            packages = [
              packages.artemis
              python
            ];
          };

          packages.default = packages.artemis;
          packages.artemis = pkgs.stdenv.mkDerivation {
            pname = "artemis";
            version = "0.0.1";
            src = ./artemis.py;

            buildInputs = [
              python
            ];

            unpackPhase = ":";

            installPhase = ''
              mkdir -p $out/bin
              cp "$src" $out/bin/artemis
              chmod +x $out/bin/artemis
            '';
          };
        }
      );
    in
    rec {
      nixosConfigurations.artemis = nixpkgs.lib.nixosSystem rec {
        system = "x86_64-linux";
        modules = [
          ({
            _module.args.artemis =
              self.outputs.packages."${system}".artemis;
            _module.args.flake = self;
            _module.args.nixpkgs = nixpkgs;
            _module.args.system = system;
          })
          "${nixpkgs}/nixos/modules/virtualisation/digital-ocean-image.nix"
          ./artemis-configuration.nix
        ];
      };

      images.artemis = nixosConfigurations.artemis.config.system.build.digitalOceanImage;
    } // systemOutputs;
}
