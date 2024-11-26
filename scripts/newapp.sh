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
            latestVersion=$(curl -s https://raw.githubusercontent.com/truecharts/public/refs/heads/master/charts/${train}/je${chart}llyfin/Chart.yaml | grep ^version:)
            echo "Found ${version}"
            chartSearch=False
        fi
    done
done

cp kubernetes-dashboard ${chart}
cd ${chart}
rm ks.yaml
cd app
rm kustomization.yaml

sed -i -e "s/version: 1.10.1/"${version}"/g" helm-release.yaml
sed -i -e "s/name: kubernetes-dashboard/name: "${chart}"/g" helm-release.yaml
sed -i -e "s/namespace: kubernetes-dashboard/namespace: "${namespace}"/g" helm-release.yaml
sed -i -e 's/loadBalancerIP: ${DASHBOARD_IP}/loadBalancerIP: YOUR IP HERE/g' helm-release.yaml

echo "verify your edits..."
nano helm-release.yaml

sed -i -e "s/name: kubernetes-dashboard/name: "${namespace}"/g" namespace.yaml
echo "verify your edits..."
nano namespace.yaml


cd ~/truecharts
clustertool genconfig
clustertool encrypt
git add -A && git commit
git push
clustertool decrypt

flux reconcile source git cluster -n flux-system
flux get kustomizations --watch