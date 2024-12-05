**Archived**: after iXsystems [shifted gears](https://forums.truenas.com/t/the-future-of-electric-eel-and-apps/5409) from including k3s in TrueNAS SCALE, to just making it a Docker[-compose] host, this became an attempt to migrate my existing configuration and services stack over to [Talos Linux](https://www.talos.dev/), running in a VM on the SCALE host. *This worked,* in sort of a proof-of-concept way; the biggest technical blocker was probably lack of a stable/straightforward CSI for my use case, but overall it kind of ventured outside of one of the original principles: "just enough Kubernetes".

So at that point, it seemed unwise to continue given the extra complication, and instead I decided to accept the change to Docker Compose. 

If any of this repo's content is helpful to you, great! If you are looking for Helm charts to run on top of Talos and other Kubernetes distributions, see [TrueCharts](https://truecharts.org).  

<br>

## :book:&nbsp; Overview
Kubernetes? At Home?
<br>
While I wouldn't fault you for saying that this is an awfully complicated way to run services at home, it allows for an incredibly straightforward pattern of being able to do anything from tinkering/developing on Kubernetes, all the way to running stuff that we depend on to store and preserve our family's photos. Therefore I like to think of it as _Just Enough Kubernetes_ - Production-worthy for our purposes, but not so out there that I'm constantly fighting with it.
<br>
<br>
What you see here, then, is the authoritative source for my cluster's configuration: 

- [ArgoCD](https://argoproj.github.io/cd/) keeps watch over this Git repository, and makes changes accordingly to the cluster based on commits. 
- Bitnami [sealed-secrets](https://github.com/bitnami-labs/sealed-secrets) is what's used to encrypt secrets in a way that allows them to be kept in a public repo.

## :robot:&nbsp; Automation

* [Renovate](https://github.com/renovatebot/renovate) keeps workloads up-to-date by scanning the repo and opening pull requests when it detects a new container image update or a new helm chart

## :handshake:&nbsp; Community

Thanks to all the people who donate their time to the [Home Operations](https://discord.com/invite/home-operations/) community.
This repo would not exist if it wasn't for the excellent people there sharing what they know.

I'd like to especially call out these community projects, which I rely on heavily:

* [Common Library Chart](https://bjw-s.github.io/helm-charts/docs/common-library/)
* [Container Images](https://github.com/onedr0p?tab=packages&repo_name=containers)

_How do I get started with my own Kubernetes @ Home project?_ It all starts with this [template.](https://github.com/onedr0p/cluster-template)