async function login(username,password){
const params = new URLSearchParams();
params.append('username', username);
params.append('password', password);

const response = await fetch(window.location.origin+'/api/login', {
	method: 'POST',
	headers: {
		'Content-Type': 'application/x-www-form-urlencoded'
	},
	body: params.toString()
});

if (response.status === 200) {
	const data = await response.json();
	mikan["token"] = data.token;
	localStorage.setItem("token",mikan["token"]);
	log('Login successful');
} else {
	log('Login failed');
}
}
async function fetchApiData(type,value="") {
const response = await fetch(window.location.origin+`/api?type=${type}&value=${encodeURIComponent(value)}`, {
	headers: {
		'Authorization': `Bearer ${mikan["token"]}`
	}
});

if (response.status===200) {
	let data=(await response.json())
	return data;
} else if (response.status === 401) {
	log('Authorization failed');
	return ;
} else {
	log('Connection failed');
	return ;
}
}
function loadToken() {
let t=localStorage.getItem("token");
if(t!=null&&t!=undefined&&t!=""){mikan["token"]=t}
}
async function checkPage(){
let query = new URLSearchParams(location.search);
if(query.has("page")&&query.has("value")){changePage(query.get("page"),query.get("value"))}
else if(query.has("page")){changePage(query.get("page"))}
}
async function changePage(page,value=""){
if(["knownseries","search"].includes(page)){
	if(value!=""&&value!=null&&typeof value=="string"){
		if(page=="knownseries"){loadSeries(value)}
		if(page=="search"){searchSeries(value)}
	}else{
		if(page=="knownseries"){loadSeries()}
		if(page=="search"){searchSeries()}
	}
}
else if(page=="settings"){showSettings()}
}
async function formWindow(arg){
let data = {
	location: document.body,
	title: "title",
	form: [
		{
			id: "input",
			type: "text",
			value: "",
			disable: false
		}
	]
}
data = {...data, ...arg};
let out = {status:"", data:{}}

const container = document.createElement("div");
const title = document.createElement("div");
const form = document.createElement("form");
const action = document.createElement("div");
const actionConfirm = document.createElement("button");
const actionCancel = document.createElement("button");

container.classList.add("formContainer");
title.classList.add("title");
form.classList.add("form");
action.classList.add("action");

form.append(title);
container.append(form);
action.append(actionConfirm,actionCancel);

title.innerHTML = data["title"];
actionConfirm.innerHTML = "Confirm";
actionConfirm.type = "submit";
actionCancel.innerHTML = "Cancel";

form.style.width="0";
form.style.padding="0";
form.style.border="none";
form.style.pointerEvents="none";

form.method = "dialog";
let formInput = [];
for(let i of data["form"]){
	const k = Object.keys(i);
	const input = document.createElement("input");
	input.type = i["type"];
	input.dataset.id = i["id"];
	if(k.includes("disable")){input.disabled = i["disable"]}
	if(k.includes("value")){input.value = i["value"]}
	form.append(input);
	formInput.push(input);
}
form.append(action);

setTimeout(()=>{
form.style.width="";
form.style.padding="";
form.style.border="";
form.style.pointerEvents="";
},40);

if(data["location"]==document.body){
	container.classList.add("center");
	document.body.append(container);
}
else{
	container.classList.add("relative");
}
container.style.opacity = "1";

return new Promise((resolve) => {
	form.addEventListener("submit", () => {
		out["status"] = "success";
		for (let i of formInput){out["data"][i.dataset.id] = i.value}
		resolve(out);
		form.style.width="0";
		form.style.padding="0";
		form.style.pointerEvents="none";
		setTimeout(()=>{container.remove()},400);
	});
	actionConfirm.addEventListener("click", () => {
		out["status"] = "success";
		for (let i of formInput){out["data"][i.dataset.id] = i.value}
		resolve(out);
		form.style.width="0";
		form.style.padding="0";
		form.style.pointerEvents="none";
		setTimeout(()=>{container.remove()},400);
	});
	actionCancel.addEventListener("click", () => {
		out["status"] = "failed";
		for (let i of formInput){out["data"][i.dataset.id] = i.value}
		resolve(out);
		form.style.width="0";
		form.style.padding="0";
		form.style.border="none";
		form.style.pointerEvents="none";
		setTimeout(()=>{container.remove()},400);
	});
});
}
async function displayTable(data,link=false,action={}){
await sortTable();
const key = [];
const colsAll = Object.keys(data[0]);
const cols = [];
const con = document.querySelector("#content");
for(let v of colsAll){
	if(v.includes("id")){key.push(v)}
	else{cols.push(v)}
}
con.innerHTML = "";
con.dataset.displayType = "table";
document.querySelector("#serieCover img").style.display="none";
document.querySelector("#serieCover img").src="";

const header = document.createElement("tr");
for (let i = 0; i < cols.length; i++) {
	const warp = document.createElement("th");
	const head = document.createElement("div");
	head.innerHTML = cols[i];
	warp.classList.add("header");
	warp.append(head);
	header.append(warp);
}

header.addEventListener("contextmenu", (e) => {
	if(e.target.closest("div").classList.contains("context")){return}
	e.preventDefault();

	const context=document.createElement("div");
	context.addEventListener("contextmenu", () => {header.removeChild(context)});
	context.classList.add("context");
	context.style.left = `${4+e.pageX - e.target.closest("tr").getBoundingClientRect().left}px`;
	context.style.top = `${4+e.pageY - e.target.closest("tr").getBoundingClientRect().top}px`;
	for (let j = 0; j < colsAll.length; j++) {
		for (const s of ["asc","desc"]){
			const contextList = document.createElement("button");
			contextList.innerHTML="Sort by \""+colsAll[j]+"\" "+s;
			contextList.addEventListener("click",async ()=>{
				if(mikan.sortLast.includes(colsAll[j])){mikan.sortLast.splice(mikan.sortLast.indexOf(colsAll[j]),1)}
				mikan.sortLast.unshift(colsAll[j]);
				mikan.sort[colsAll[j]]=s;
				displayTable(data,link,action);
				header.removeChild(context)
			})
			context.append(contextList)
		}
	}
	document.querySelectorAll(".context").forEach(c=>{c.parentNode.removeChild(c)})
	header.append(context);
});
con.append(header);

for (let i = 0; i < data.length; i++) {
	const fi = document.createElement("tr");
	fi.dataset["row"] = i+1;
	fi.dataset["select"] = "false";
	for(const id of key){fi.dataset[id] = data[i][id]}
	fi.addEventListener("click",()=>{if(fi.dataset["select"]!="true"){document.querySelectorAll("#content tr").forEach(e=>{e.dataset["select"]="false"});fi.dataset["select"]="true";if(typeof fi.dataset["serieid"]=="string"){document.querySelector("#serieCover img").style.display="";document.querySelector("#serieCover img").src="/api?type=getcover&value="+fi.dataset["serieid"]}else{document.querySelector("#serieCover img").style.display="none";document.querySelector("#serieCover img").src=""}}})
	con.append(fi);
	const url = new URL(location);
	for (let d = 0; d < cols.length; d++) {
		const warp = document.createElement("td");
		const info = link ? document.createElement("a") : document.createElement("div");
		info.append(data[i][cols[d]]=="" ? " " : data[i][cols[d]]);
		info.title = data[i][cols[d]].innerText||data[i][cols[d]].value||data[i][cols[d]]||data[i][cols[d-1]];
		info.dataset["row"] = i+1;
		if(link){
			info.tabIndex=0;
			url.searchParams.set("value", data[i][key[0]]);
			info.addEventListener("click",()=>{if(fi.dataset["select"]=="true"){history.pushState({page:url.searchParams.get("page"),value:key[0]},"", url);checkPage()}})
		}
		warp.append(info);
		fi.append(warp);
	}
	
	const acKey=Object.keys(action);
	if(acKey.length>0){
		fi.addEventListener("contextmenu", (e) => {
		fi.click();
		if(e.target.closest("div").classList.contains("context")){return}
		e.preventDefault();

		const context=document.createElement("div");
		context.addEventListener("click", () => {fi.removeChild(context)});
		context.addEventListener("contextmenu", () => {fi.removeChild(context)});
		context.classList.add("context");
		context.style.left = `${4+e.pageX - e.target.closest("tr").getBoundingClientRect().left}px`;
		context.style.top = `${4+e.pageY - e.target.closest("tr").getBoundingClientRect().top}px`;
		for (let j = 0; j < acKey.length; j++) {
			const contextList = document.createElement("button");
			contextList.innerHTML = action[acKey[j]];
			contextList.addEventListener("click",()=>{tableAction(acKey[j],data[i]["serieid"]);fi.removeChild(context)})
			context.append(contextList)
		}
		document.querySelectorAll(".context").forEach(c=>{c.parentNode.removeChild(c)})
		fi.append(context);
		});
	}
	con.append(fi);
}
}
async function sortTable() {
const tsort = mikan.sort;
const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' });

mikan.tableData.sort((a, b) => {
	for (const key of mikan.sortLast) {
		if (key in a && key in b) {
			const order = tsort[key];
			const comparison = collator.compare(a[key], b[key]);
			if (comparison !== 0) {
				return order === "asc" ? comparison : -comparison;
			}
		}
	}
	return 0;
})
}
async function loadSeries(value=""){
if(value!=""&&value!=null&&typeof value=="string"){
	mikan.tableData = (await fetchApiData("knownserieschapter",value))["data"];
	displayTable(mikan.tableData)
}else{
	mikan.tableData = (await fetchApiData("knownseries"))["data"];
	displayTable(mikan.tableData,true,{dlLast:"Download until lastest chapter",updateSerie:'Update serie info to lastest',updateCover:'Update to lastest cover',forceName:'Force save serie name'})
}
}
async function searchSeries(){
const searchValue = await formWindow({title:"Search",form:[{id:"search",type:"text"}]});
if(searchValue["status"]=="success"){
	const data = (await fetchApiData("search",searchValue["data"]["search"]))["data"];
	displayTable(data,false,{addSerie:"Add this manga"})
}
}
async function tableAction(action,value){
log("tableAction act:"+action+" val:"+value,true)
if(action=="addSerie"){
fetchApiData("addserie",value)
} else if(action=="updateSerie"){
fetchApiData("updateserie",value)
} else if(action=="dlLast"){
fetchApiData("dllast",value)
} else if(action=="updateCover"){
fetchApiData("updatecover",value)
} else if(action=="forceName"){
const info = await formWindow({title:"Force use name", form:[{id:"name",type:"text"}]})
if(info["status"]=="success"){
fetchApiData("updateforcename",JSON.stringify({id:value,name:info["data"]["name"]}))
}
}
}
async function log(value,trance=false){
if((trance==true&&mikan.debug==true)||trance==false){
const date = new Date();
const dateFormat = date.toISOString().slice(0, 10)+" "+date.toTimeString().slice(0,8);
value="["+dateFormat+"] "+value;
console.log(value);
const txt=document.createElement("p");
txt.innerHTML=value.toString();
const logEle=document.querySelector("#log>div:nth-child(2)");
logEle.append(txt);
logEle.scrollTop = logEle.scrollHeight
}
if(mikan.debug==true){document.querySelector("#log").style.height="calc(60% - 10rem)"}else{document.querySelector("#log").style.height=""}
}
async function showSettings(){
let data = (await fetchApiData("getsettings"))["data"];
data.forEach(e=>{
	let v=e.value;
	e.value=document.createElement("input");
	e.value.value=v;
})
let save=document.createElement("button");
save.addEventListener("click",saveSettings);
save.innerHTML="Save";
data.push({id:"saveSetting",name:"Save Settings",value:save});
displayTable(data)
}
async function saveSettings(){
const url = new URL(location);
if("settings"==url.searchParams.get("page")){
	let list=document.querySelectorAll("#content [data-id]:not([data-id=saveSetting]");
	let data=[];
	for (let i = 0; i < list.length; i++){
		data.push({id:list[i].dataset.id,value:list[i].querySelector("input").value})
	}
	fetchApiData("setsettings",JSON.stringify(data));
	log("save settings: "+JSON.stringify(data),true)
}
}


mikan={};
mikan.sort={};
mikan.sortLast=[];
mikan.debug=true;
loadToken()
checkPage()

document.querySelector("#app > header > button:nth-child(1)").addEventListener("click", () => {
	const nav = document.querySelector("#container > nav");
	nav.style.width = nav.style.width === '' ? '0' : '';
	nav.style.padding = nav.style.padding === '' ? '0' : '';
	nav.style.visibility = nav.style.visibility === '' ? 'hidden' : '';
});
document.querySelectorAll("nav>button").forEach(n => {if(n.id!="log"){
	const url = new URL(location);
	url.searchParams.set("page", n.value);
	url.searchParams.set("value", "");
	n.addEventListener("click",()=>{history.pushState({page:n.value,value:""}, "", url);checkPage()})
}});
window.addEventListener('popstate', checkPage);
document.querySelector("#login").addEventListener('click', async () => {
	const info = await formWindow({title:"Login", form:[{id:"username",type:"text"},{id:"password",type:"password"}]})
	if(info["status"]=="success"){
		login(info["data"]["username"],info["data"]["password"])
	}
});
log("script loaded");