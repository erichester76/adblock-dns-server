Vagrant.configure("2") do |config|
  config.vm.box = "ubuntu/xenial64"

  config.vm.provider "virtualbox" do |vb|
    vb.gui = false
    vb.memory = "640"
  end

  config.vm.provision "shell", inline: <<-SHELL
    apt-get purge -y snapd lxcfs lxd ed ftp ufw accountsservice policykit-1
    apt-get autoremove -y
    apt-get update
    apt-get install -y dnsutils htop python3 python3-dev virtualenv redis-server redis-tools
    apt-get upgrade -y
    sed -ri 's/^bind /#&/;s/^(port ).*$/\\10/;s/^# (unixsocket)/\\1/;s/^(unixsocketperm )[0-9]+/\\1777/' /etc/redis/redis.conf
    systemctl restart redis-server.service
  SHELL
end
