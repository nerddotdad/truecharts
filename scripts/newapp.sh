#!/bin/bash
# building this to help me with basic tasks in my cluster
chartSearch=True

cd ~/truecharts/clusters/main/kubernetes/apps

read -p "Enter new chart name: " chart
echo "locating truecharts chart"
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

sed -i -e "s/version: 1.10.1/"${latestVersion}"/g" helm-release.yaml
sed -i -e "s/name: kubernetes-dashboard/name: "${chart}"/g" helm-release.yaml
sed -i -e "s/namespace: kubernetes-dashboard/namespace: "${namespace}"/g" helm-release.yaml
sed -i -e 's/loadBalancerIP: ${DASHBOARD_IP}/loadBalancerIP: YOUR IP HERE/g' helm-release.yaml

cat helm-release.yaml
echo "please ensure you update the loadbalancer IP..."
sleep 10
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