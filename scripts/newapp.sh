#!/bin/bash
# building this to help me with basic tasks in my cluster
chartSearch=True

cd ~/truecharts/clusters/main/kubernetes/apps

read -p "Enter new chart name: " chart
read -p "Enter the namespace you'd like to put this chart in: " namespace

while [ $chartSearch == True ]
do
    for train in incubator library premium stable system
    do
        chartSearch=$(curl -s -o /dev/null -w "%{http_code}" --head https://truecharts.org/charts/${train}/${chart}/)
        if [ $chartSearch == 404 ]
        then
            echo "Chart not found on $train train."
        else
            echo "Chart found on $train train."
            latestVersion=$(curl -s https://raw.githubusercontent.com/truecharts/public/refs/heads/master/charts/${train}/${chart}/Chart.yaml | grep ^version:)
            echo "Found ${latestVersion}"
            chartSearch=False
        fi
    done
done

cp -r kubernetes-dashboard ${chart}
cd ${chart}
rm ks.yaml
cd app
rm kustomization.yaml

sed -i -e "s/name: kubernetes-dashboard/name: ${chart}/g" helm-release.yaml
sed -i -e "s/namespace: kubernetes-dashboard/namespace: ${namespace}/g" helm-release.yaml
sed -i -e "s/chart: kubernetes-dashboard/chart: ${chart}/g" helm-release.yaml
sed -i -e "s/version: 1.10.1/${latestVersion}/g" helm-release.yaml

while true; do

read -p "Would you like to add a loadbalancer ip? (y/n) " yn

case $yn in 
	[yY] )
    read -p "please enter the ip you'd like to expose to your INTERNAL network (usually 192,168.x.x)" ip
    sed -i -e "s/loadBalancerIP: \${DASHBOARD_IP}/loadBalancerIP: ${ip}/g" helm-release.yaml
	break
    ;;
	[nN] )
    echo "Commenting out the values section. Please be sure to come back and edit it later!"
    sed -i '/^  values:$/s/^/#/' helm-release.yaml
    sed -i '/^    service:$/s/^/#/' helm-release.yaml
    sed -i '/^      main:$/s/^/#/' helm-release.yaml
    sed -i '/^        type: LoadBalancer$/s/^/#/' helm-release.yaml
    sed -i '/^        loadBalancerIP: ${DASHBOARD_IP}$/s/^/#/' helm-release.yaml
    sed -i '/^        ports:$/s/^/#/' helm-release.yaml
    sed -i '/^          main:$/s/^/#/' helm-release.yaml
    sed -i '/^            port: 80$/s/^/#/' helm-release.yaml
    break
    ;;
	* ) echo invalid response;;
esac

done

cat helm-release.yaml
read -p "does this look correct? (y/ctrl+c to quit)" helmVerify
if [ $helmVerify != "y" ]
then
    nano helm-release.yaml
fi

sed -i -e "s/name: kubernetes-dashboard/name: "${namespace}"/g" namespace.yaml
cat namespace.yaml
read -p "does this look correct? (y/ctrl+c to quit)" namespaceVerify
if [ $namespaceVerify != "y" ]
then
    nano namespace.yaml
fi

cd ~/truecharts
clustertool genconfig
clustertool encrypt
git add -A && git commit
git push
clustertool decrypt

flux reconcile source git cluster -n flux-system
flux get kustomizations --watch