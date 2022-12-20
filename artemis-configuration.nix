{ pkgs
, flake
, artemis
, ...
}:
let
  artemisDir = "/var/lib/artemis";
in
{
  environment.systemPackages = with pkgs; [
    git
    vim
  ];

  networking.firewall.allowedTCPPorts = [
    22
  ];

  services.sshd.enable = true;

  system.stateVersion = "22.11";

  systemd.services.artemis = {
    after = [ "network.target " ];
    wantedBy = [ "multi-user.target" ];
    description = "Start up the Artemis listener.";

    serviceConfig = {
      ExecStart = "${artemis}/bin/artemis";
      Restart = "on-failure";
      DynamicUser = true;
      WorkingDirectory = "/var/lib/artemis";
      StateDirectory = "artemis";

      LockPersonality = true;
      MemoryDenyWriteExecute = true;
      NoNewPrivileges = true;
      PrivateDevices = true;
      PrivateTmp = true;
      ProtectClock = true;
      ProtectControlGroups = true;
      ProtectHome = true;
      ProtectKernelLogs = true;
      ProtectKernelModules = true;
      ProtectKernelTunables = true;
      ProtectProc = "invisible";
      ProtectSystem = "strict";
      RemoveIPC = true;
      RestrictAddressFamilies = [ "AF_UNIX" "AF_INET" "AF_INET6" ];
      RestrictNamespaces = true;
      RestrictRealtime = true;
      RestrictSUIDSGID = true;

    };
  };

  virtualisation.digitalOceanImage.configFile = ./artemis-configuration.nix;
  virtualisation.digitalOceanImage.compressionMethod = "bzip2";
}
