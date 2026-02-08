async function login(arg){
let checkInput = checkArg({
	input:arg,
	context:[
		{var:"username", type:"string", req:true},
		{var:"password", type:"string", req:true}
	]
});
if(checkInput["status"]=="failed"){
	mikan.login=false;
	log('Login failed. '+checkInput["data"]["msg"]);
	throw new Error(checkInput["data"]["msg"]);
}
arg=checkInput["data"]["normal"];

const params = new URLSearchParams();
params.append('username', arg["username"]);
params.append('password', arg["password"]);

const response = await fetch(mikan["server"]+'/api/login', {
	method: 'POST',
	headers: {
		'Content-Type': 'application/x-www-form-urlencoded'
	},
	body: params.toString()
});

if (response.status === 200) {
	const data = await response.json();
	mikan["token"] = data.token;
	localStorage.setItem("token",JSON.stringify(mikan["token"]));
	mikan.login=true;
	document.querySelector(".loginlogout").classList.add("login")
	log('Login successful');
	checklogin1st();
} else {
	mikan.login=false;
	log('Login failed');
}
}
async function logout(){
	localStorage.removeItem("token");
	window.location.reload();
}
async function fetchApiData(arg) {
let checkInput = checkArg({
	input:arg,
	context:[
		{var:"type", type:"string", req:true},
		{var:"valueObj", type:"object"},
		{var:"requestType", type:"string", def:"get"}
	]
});
if(checkInput["status"]=="failed"){
	throw new Error(checkInput["data"]["msg"]);
}
arg=checkInput["data"]["normal"];

let response;
if(arg["requestType"].toLowerCase() == "get"){
if(Object.keys(arg["valueObj"]).length > 0){
let api = new URL(mikan["server"]+"/api");
api.search = new URLSearchParams(arg["valueObj"]);
response = await fetch(api, {
	headers: {
		'Authorization': `Bearer ${mikan["token"]}`
	}
});
}
else{
response = await fetch(mikan["server"]+`/api?type=`+arg["type"], {
	headers: {
		'Authorization': `Bearer ${mikan["token"]}`
	}
});
}
}
else if(arg["requestType"].toLowerCase() == "post"){
if(Object.keys(arg["valueObj"]).length > 0){
response = await fetch(mikan["server"]+`/api?type=`+arg["type"], {
	method: 'POST',
	headers: {
		'Authorization': `Bearer ${mikan["token"]}`
	},
	body: JSON.stringify(arg["valueObj"])
});
}
else{
response = await fetch(mikan["server"]+`/api?type=`+arg["type"], {
	method: 'POST',
	headers: {
		'Authorization': `Bearer ${mikan["token"]}`
	}
});
}

}

if (response.status===200) {
	mikan.login=true;
	let data;
	try {
		data=(await response.json())
	} catch {
		data=(response.body)
	}
	return data;
} else if (response.status === 401) {
	mikan.login=false;
	log('Authorization failed');
	return ;
} else {
	log('Connection failed');
	return ;
}
}
async function serverEvent() {
let retryCount = 0;
let waitTime = 1000;
const maxWaitTime = 300000;

async function connect() {
try {
	const response = await fetch(mikan["server"]+`/api/log`, {
		headers: {
			'Authorization': `Bearer ${mikan["token"]}`,
			"Accept": "text/event-stream",
			"Cache-Control": "no-cache",
			"Connection": "keep-alive"
		}
	});

	if (response.status === 200) {
		log('Connected to server log');

		const reader = response.body.getReader();
		const decoder = new TextDecoder();
		let buffer = "";

		while (true) {
			const {value, done} = await reader.read();
			if (done) {
				log('Server connection closed');
				throw new Error('Connection closed');
			}
			
			buffer += decoder.decode(value, {stream: true});
			const lines = buffer.split('\n\n');
			buffer = lines.pop() || '';

			for(let line of lines) {
				if(line.trim().length > 0) {
					try {
						const match = line.match(/^data: (.+)$/m);
						if (match) {
							const data = JSON.parse(match[1]);
							if(data["type"] == "text") {
								log("["+data["timestamp"]+" server time] "+data["data"]);
							}
							else if(data["type"] == "progress") {
								mikan.progress = JSON.parse(data["data"]);
								showProgress();
							}
							else {
								log(data);
							}
						}
					} catch(e) {
						log(`Error parsing message: ${e.message}`);
					}
				}
			}
		}
	} else if (response.status === 401) {
		log('Authorization failed');
		mikan.login = false;
		throw new Error('Authorization failed');
	} else {
		throw new Error('Connection failed');
	}

} catch(error) {
	log(`Error in server connection: ${error.message}`);
	checklogin1st();
	log(`Reconnecting in ${waitTime/1000}s...`);
	retryCount++;
	waitTime = Math.min((waitTime * 1.5).toFixed(2), maxWaitTime);
	
	await new Promise(resolve => setTimeout(resolve, waitTime));
	await connect();
}
}

await connect();
}
function loadToken() {
let t=JSON.parse(localStorage.getItem("token"));
if(t!=null&&t!=undefined&&t!=""){mikan["token"]=t}
}
async function checkPage(){
let query = new URLSearchParams(location.search);
if(query.has("page")&&query.has("value")){changePage({page:query.get("page"),value:query.get("value")})}
else if(query.has("page")){changePage({page:query.get("page")})}
}
async function changePage(arg){
let checkInput = checkArg({
	input:arg,
	context:[
		{var:"page", type:"string", req:true},
		{var:"value", type:"string"}
	]
});
if(checkInput["status"]=="failed"){
	throw new Error(checkInput["data"]["msg"]);
}
arg=checkInput["data"]["normal"];

if(["knownseries","search","knowngroups"].includes(arg["page"])){
	if(arg["value"]!=""){
		if(arg["page"]=="knownseries"){loadSeries({value:arg["value"]})}
		if(arg["page"]=="search"){searchSeries({value:arg["value"]})}
		if(arg["page"]=="knowngroups"){loadGroups()}
	}else{
		if(arg["page"]=="knownseries"){loadSeries()}
		if(arg["page"]=="search"){searchSeries()}
		if(arg["page"]=="knowngroups"){loadGroups()}
	}
}
else if(arg["page"]=="settings"){showSettings()}
else if(arg["page"]=="progress"){showProgress()}
}
async function formWindow(arg){
let def = {
	location: document.body,
	title: "title",
	id: "form",
	form: [
		{
			id: "input",
			type: "text",
			value: "",
			name: "",
			disable: false
		}
	]
};
let out = {status:"", data:{}};

let checkInput = checkArg({
	input:arg,
	context:[
		{var:"id", type:"string", def:"formWindow"},
		{var:"location", type:"object", def:(document.body)},
		{var:"title", type:"string"},
		{var:"form", type:"array", req:true}
	]
});
if(checkInput["status"]=="failed"){
	throw new Error(checkInput["data"]["msg"]);
}
arg=checkInput["data"]["normal"];

document.querySelectorAll(".formContainer.form[data-id='"+arg["id"]+"'").forEach(e=>e.cancel());

const title = document.createElement("div");
const form = document.createElement("form");
const inputData = document.createElement("div");
const action = document.createElement("div");
const actionConfirm = document.createElement("button");
const actionCancel = document.createElement("button");

form.classList.add("formContainer");
title.classList.add("title");
form.classList.add("form");
inputData.classList.add("inputData");
action.classList.add("action");
form.classList.add("center");


form.dataset.id = arg["id"];
title.innerHTML = arg["title"];
actionConfirm.innerHTML = "Confirm";
actionConfirm.type = "submit";
actionCancel.innerHTML = "Cancel";

form.style.width="0";
form.style.padding="0";
form.style.border="none";
form.style.pointerEvents="none";

setTimeout(()=>{
form.style.width="";
form.style.padding="";
form.style.border="";
form.style.pointerEvents="";
},40);

form.append(title);
form.append(inputData);
action.append(actionConfirm,actionCancel);
form.append(action);
document.body.append(form);

form.method = "dialog";
let formInput = [];
for(let i of arg["form"]){
	const k = Object.keys(i);
	let input = document.createElement("input");
	const inputLabel = document.createElement("label");
	input.type = i["type"];
	input.dataset.id = i["id"];
	if(k.includes("name")){inputLabel.innerHTML = i["name"]+": "}
	if(k.includes("disable")){input.disabled = i["disable"]}
	if(k.includes("value")){input.value = i["value"]}
	if(k.includes("value")&&i["type"]=="checkbox"){input.checked = Boolean(i["value"])}
	if(k.includes("value")&&i["type"]=="select"){
		input = document.createElement("select");
		input.dataset.id = i["id"];
		const option = i["value"].split(",");
		for (let o=0; o<option.length;o++) {
			const selectOption = document.createElement("option");
			selectOption.value = option[o];
			selectOption.innerHTML = option[o];
			input.append(selectOption);
		}
	}
	inputLabel.append(input);
	inputData.append(inputLabel);
	formInput.push(input);
	await new Promise(s => setTimeout(s, 40));
}


return new Promise((resolve) => {
	form.addEventListener("submit", () => {
		out["status"] = "success";
		for (let i of formInput){
			out["data"][i.dataset.id] = i.value;
			if(i.type=="checkbox"){out["data"][i.dataset.id] = i.checked}
		}
		resolve(out);
		form.classList.add("remove");
		setTimeout(()=>{form.remove()},400);
	});
	actionConfirm.addEventListener("click", () => {
		out["status"] = "success";
		for (let i of formInput){
			out["data"][i.dataset.id] = i.value;
			if(i.type=="checkbox"){out["data"][i.dataset.id] = i.checked}
		}
		resolve(out);
		form.classList.add("remove");
		setTimeout(()=>{form.remove()},400);
	});
	actionCancel.addEventListener("click", () => {
		out["status"] = "failed";
		for (let i of formInput){
			out["data"][i.dataset.id] = i.value;
			if(i.type=="checkbox"){out["data"][i.dataset.id] = i.checked}
		}
		resolve(out);
		form.classList.add("remove");
		setTimeout(()=>{form.remove()},400);
	});
	form.cancel = () => {
		out["status"] = "failed";
		for (let i of formInput){
			out["data"][i.dataset.id] = i.value;
			if(i.type=="checkbox"){out["data"][i.dataset.id] = i.checked}
		}
		resolve(out);
		form.classList.add("remove");
		setTimeout(()=>{form.remove()},400);
	};
});
}
async function displayTable(arg){
let checkInput = checkArg({
	input:arg,
	context:[
		{var:"data",type:"array",def:[]},
		{var:"link", type:"boolean", def:false},
		{var:"action", type:"object"},
		{var:"moreaction", type:"object", def:mikan.moreActionDef}
	]
});
if(checkInput["status"]=="failed"){
	throw new Error(checkInput["data"]["msg"]);
}
arg=checkInput["data"]["normal"];

if(arg.data.length==0){
	mikan.moreAction = mikan.moreActionDef;
	document.querySelector("#content").innerHTML="";
	return
}
mikan.moreAction = Object.assign({},arg.moreaction,mikan.moreActionDef);
mikan.tableData = arg.data;
await sortTable();
const key = [];
const colsAll = Object.keys(arg.data[0]);
const cols = [];
const con = document.querySelector("#content");
for(let v of colsAll){
	if(v.includes("provider")){key.push(v);cols.push(v)}
	else if(v.includes("id")){key.push(v)}
	else if(v.includes("action")!=true){cols.push(v)}
}
const colsLength = cols.length;
document.querySelector("#contentBar>#searchdata").value = "";
con.innerHTML = "";
con.dataset.displayType = "table";
document.querySelector("#serieCover").classList.add("empty");
document.querySelector("#serieCover img").src="";
document.body.style.removeProperty("--background");


let dataLen = []
let dataLenMax = (100/(colsLength-1))*.9;
let dataLenMin = 20;
let dataLenNormal = false;
for (const k of cols) {arg.data[0][k] != null ? dataLen.push(arg.data[0][k].toString().length>dataLenMin?arg.data[0][k].toString().length:dataLenMin) : dataLen.push(dataLenMin) }
function tableNormal(){
for (let i=0; (i<10)&&(dataLenNormal!=true); i++) {
let r = dataLen.reduce((sum,val)=>sum+val,0);
dataLen=dataLen.map(val => ((Math.ceil(((val/r)*100)))>dataLenMax?dataLenMax:(Math.ceil(((val/r)*100)))));
dataLenNormal = !(dataLen.some(n => n>50)||(dataLen.reduce((sum,val)=>sum+val,0))<98);
}
con.style.setProperty("--col-template", dataLen.slice(0,-1).map(n=>n.toFixed(2)+"%").join(" ")+" auto");
}
tableNormal();

const header = document.createElement("div");
header.classList.add("header");
con.append(header);
for (let i = 0; i < colsLength; i++) {
	const head = document.createElement("div");
	head.innerHTML = cols[i];
	head.dataset.head = cols[i];
	head.dataset.filter = "";
	head.title = cols[i];
	head.classList.add("header");
	head.tabIndex=0;
	head.addEventListener("click",async(e)=>{if(head.dataset["select"]!="true"){
		document.querySelectorAll("#content .header[data-select=true]").forEach(e=>{e.dataset["select"]="false"});
		head.dataset["select"]="true";
	}else if(head.dataset["select"]=="true"){
		e.preventDefault();
		head.dataset["select"]="false";
	}});
	let cc = {}
	for (let j=0; j<colsAll.length; j++) {
		for (const s of ["asc","desc"]){
			cc["Sort by \""+colsAll[j]+"\" "+s] = {
				name: "Sort by \""+colsAll[j]+"\" "+s,
				action: ()=>{
					if(mikan.sortLast.includes(colsAll[j])){mikan.sortLast.splice(mikan.sortLast.indexOf(colsAll[j]),1)}
					mikan.sortLast.unshift(colsAll[j]);
					mikan.sort[colsAll[j]]=s;
					displayTable(arg);
				}
			};
		}
	}

	head.addEventListener("contextmenu", (e) => {contextMenu({id:"tableHeader",location:head,event:e,context:cc})});
	header.append(head);
}

const dataSec = document.createElement("div");
dataSec.classList.add("data");
con.append(dataSec);
dataLen = Array.from({length: colsLength},()=>0);
const dataLoad = new IntersectionObserver(entries => {
	entries.forEach(entry => {entry.target.style.visibility = entry.isIntersecting ? 'visible' : 'hidden'});
}, {
	root: dataSec,
	rootMargin: '100%',
	threshold: 0
});
const dataLength = arg["data"].length;
for (let i=0; i<arg["data"].length; i++) {
	const url = new URL(location);
	for (let d = 0; d < colsLength; d++) {
		if(arg["data"][i][cols[d]]==null){arg["data"][i][cols[d]]=""}
		dataLen[d] = dataLen[d] + (arg["data"][i][cols[d]].toString().length>dataLenMin?arg["data"][i][cols[d]].toString().length:dataLenMin);
		dataLenNormal = false;
		const dataCol = arg.link ? document.createElement("a") : document.createElement("div");
		dataCol.append(arg["data"][i][cols[d]]=="" ? " " : arg["data"][i][cols[d]]);
		dataCol.title = arg["data"][i][cols[d]].innerText||arg["data"][i][cols[d]].value||arg["data"][i][cols[d]]||arg["data"][i][cols[d-1]];
		dataCol.dataset["row"] = i+1;
		dataCol.dataset["select"] = "false";
		dataCol.dataset["cols"] = cols[d];
		dataCol.dataset["colsdata"] = arg["data"][i][cols[d]].innerText || String(arg["data"][i][cols[d]]);
		dataCol.tabIndex=0;
		if(arg.link){
			url.searchParams.set("value", arg["data"][i][key[0]]);
			dataCol.addEventListener("click",()=>{if(dataCol.dataset["select"]=="true"){history.pushState({page:url.searchParams.get("page"),value:key[0]},"", url);checkPage()}})
		}

		for(const id of key){dataCol.dataset[id] = arg["data"][i][id]}
		dataCol.selected = async()=>{if(dataCol.dataset["select"]!="true"){
			document.querySelectorAll("#content .data > *[data-select=true]").forEach(e=>{e.dataset["select"]="false"});
			document.querySelectorAll("#content .data > *[data-row='"+dataCol.dataset["row"]+"']").forEach(e=>{e.dataset["select"]="true"});
			if(typeof dataCol.dataset["serieid"]=="string"){
				document.querySelector("#serieCover").classList.remove("empty");
				document.querySelector("#serieCover img").src="/api?type=getcover&id="+dataCol.dataset["serieid"]+"&provider="+dataCol.dataset["provider"];
				document.body.style.setProperty("--background", "url(/api?type=getcover&id="+dataCol.dataset["serieid"]+"&provider="+dataCol.dataset["provider"]+")");
			}else{
				document.querySelector("#serieCover").classList.add("empty");
				document.querySelector("#serieCover img").src="";
				document.body.style.removeProperty("--background");
			}
		}}
		dataCol.addEventListener("click",dataCol.selected)

		let cc = []
		if("action" in arg["data"][i]){
		for(const ac of arg["data"][i]["action"]){
			cc[ac["name"]] = {
				name: ac["name"],
				action: ()=>ac["func"]()
			};
		}
		dataCol.addEventListener("contextmenu", (e) => {dataCol.selected();contextMenu({id:"tableDataRow"+(i+1),location:dataCol,event:e,context:cc})})
		}
		dataSec.append(dataCol);
		dataLoad.observe(dataCol);
	}
	document.querySelector("#contentBar>#sort").onclick=()=>{sortTableData({data:arg.data,link:arg.link,action:arg.action})};
	document.querySelector("#contentBar>#filter").onclick=()=>{filterTableData()};
	document.querySelector("#contentBar>#searchdata").oninput=(e)=>{searchTableData(e.target.value)};
}
const dataScroll = document.createElement("div");
const dataScroller = document.createElement("div");
dataScroll.classList.add("scrollbar");
dataScroller.classList.add("scroller");
dataScroll.style.height = dataSec.offsetHeight+"px";
dataScroller.style.height = dataSec.scrollHeight+"px";
window.addEventListener("resize",()=>{
	dataScroll.style.height = dataSec.offsetHeight+"px";
	dataScroller.style.height = dataSec.scrollHeight+"px";
});
let scon = setTimeout(()=>{dataScroll.style.opacity=""},400);
let sconf = ()=>{clearTimeout(scon);scon=setTimeout(()=>{dataScroll.style.opacity=""},400);}
let scrollt = setTimeout(()=>{dataSec.addEventListener("scroll",sec);dataSec.addEventListener("scrollend",sece)},200);
let sect = setTimeout(()=>{dataScroll.addEventListener("scroll",scroll);dataSec.addEventListener("scrollend",scrolle)},200);
let scroll = ()=>{sconf();dataScroll.style.opacity=1;dataSec.scrollTop=dataScroll.scrollTop;dataSec.removeEventListener("scroll",sec);dataSec.removeEventListener("scroll",sece)};
let sec = ()=>{sconf();dataScroll.style.opacity=1;dataScroll.scrollTop=dataSec.scrollTop;dataSec.removeEventListener("scroll",scroll);dataSec.removeEventListener("scroll",scrolle)};
let scrolle = ()=>{clearTimeout(scrollt);scrollt=setTimeout(()=>{dataSec.addEventListener("scroll",sec);dataSec.addEventListener("scrollend",sece)},200);};
let sece = ()=>{clearTimeout(sect);sect=setTimeout(()=>{dataScroll.addEventListener("scroll",scroll);dataSec.addEventListener("scrollend",scrolle)},200);};
dataScroll.addEventListener("scroll",scroll)
dataSec.addEventListener("scroll",sec)
dataScroll.addEventListener("scrollend",scrolle)
dataSec.addEventListener("scrollend",sece)
dataScroll.append(dataScroller);
con.append(dataScroll);
tableNormal();
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
async function loadSeries(arg){
let checkInput = checkArg({
	input:arg,
	context:[{var:"value", type:"string",}
	]
});
if(checkInput["status"]=="failed"){
	throw new Error(checkInput["data"]["msg"]);
}
arg=checkInput["data"]["normal"];
if(arg["value"]!=""){
	
	mikan.tableData = (await fetchApiData({type:"knownserieschapter",valueObj:{type:"knownserieschapter",value:arg["value"]}}))["data"].map(e=>{e["action"]=[
		{
			name:"Download chapter",
			func:()=>{
				log("tableAction act:"+"dlchapter"+" val:"+e["chapterid"],true);
				fetchApiData({type:"dlchapter",valueObj:{type:"dlchapter",id:e["chapterid"],serie:e["serieid"]}})
			}
		},
	];return e});
	displayTable({data:mikan.tableData})
}else{
	mikan.tableData = (await fetchApiData({type:"knownseries"}))["data"].map(e=>{if("h" in e){e.h=Boolean(e.h).toString();return e}}).map(e=>{e["action"]=[
		{
			name:"Update to lastest chapter and download",
			func: ()=>{
				log("tableAction act:"+"updateanddllast"+" val:"+e["serieid"],true);
				fetchApiData({type:"updateanddllast",valueObj:{type:"updateanddllast",provider:e["provider"],id:e["serieid"]}})
			}
		},
		{
			name:"Update to lastest chapter",
			func: ()=>{
				log("tableAction act:"+"updatechapter"+" val:"+e["serieid"],true);
				fetchApiData({type:"updatechapter",valueObj:{type:"updatechapter",provider:e["provider"],id:e["serieid"]}})
			}
		},
		{
			name:"Download until lastest chapter",
			func: ()=>{
				log("tableAction act:"+"dllast"+" val:"+e["serieid"],true);
				fetchApiData({type:"dllast",valueObj:{type:"dllast",provider:e["provider"],id:e["serieid"]}})
			}
		},
		{
			name:"Update serie info to lastest",
			func: ()=>{
				log("tableAction act:"+"updateserie"+" val:"+e["serieid"],true);
				fetchApiData({type:"updateserie",valueObj:{type:"updateserie",provider:e["provider"],id:e["serieid"]}})
			}
		},
		{
			name:"Update to lastest cover",
			func: ()=>{
				log("tableAction act:"+"updatecover"+" val:"+e["serieid"],true);
				fetchApiData({type:"updatecover",valueObj:{type:"updatecover",provider:e["provider"],id:e["serieid"]}})
			}
		},
		{
			name:"Force save serie name",
			func: async ()=>{
				log("tableAction act:"+"forceName"+" val:"+e["serieid"],true);
				const info = await formWindow({title:"Force use name", form:[{id:"name",name:"force name",type:"text"}]})
				if(info["status"]=="success"){fetchApiData({requestType:"post",type:"updateforcename",valueObj:{id:e["serieid"],provider:e["provider"],forceName:info["data"]["name"]}})}
			}
		},
		{
			name:"Mark H",
			func: async ()=>{
				log("tableAction act:"+"markH"+" val:"+e["serieid"],true);
				const markValue = await formWindow({title:"H",form:[{id:"markh",name:"h",type:"checkbox",value:e["h"]=="true"?true:false}]});
				if(markValue["status"]=="success"){await fetchApiData({requestType:"post",type:"markh",valueObj:{id:e["serieid"],provider:e["provider"],h: markValue["data"]["markh"]}});checkPage()}
			}
		},
	];return e});
	displayTable({data:mikan.tableData,link:true,moreaction:{"checkallseries": {name:"Check all series chapter", action:()=>{fetchApiData({type:"updateallserieschapter"})}}}})
}
}
async function searchSeries(arg){
let checkInput = checkArg({
	input:arg,
	context:[
		{var:"value", type:"string"},
		{var:"provider", type:"string"}
	]
});
if(checkInput["status"]=="failed"){
	throw new Error(checkInput["data"]["msg"]);
}
arg=checkInput["data"]["normal"];
if(arg["value"]==""){
	const searchValue = await formWindow({title:"Search",form:[{id:"value",name:"search",type:"text"},{id:"provider",name:"provider",type:"select",value:"mangadex"}]});
	if(searchValue["status"]=="success"){
		searchValue["data"]["type"]="search";
		const url = new URL(location);
		url.searchParams.set("value", searchValue["data"]);
		history.pushState({page:"search",value:searchValue["data"]},"", url);
		const data = (await fetchApiData({type:"search",valueObj:searchValue["data"]}))["data"].map(e=>{e["action"]=[
			{
				name:"Add this manga",
				func: ()=>{
					log("tableAction act:"+"addserie"+" val:"+e["serieid"],true);
					fetchApiData({type:"addserie",valueObj:{type:"addserie",provider:e["provider"],id:e["serieid"]}})
				}
			}
		];return e});
		displayTable({data:data})
	}
}else if(arg["value"]!=""&&arg["provider"]!=""){
	const url = new URL(location);
	url.searchParams.set("value", arg["value"]);
	history.pushState({page:"search",value:arg["value"]},"", url)
	const data = (await fetchApiData({type:"search",valueObj:arg}))["data"];
	displayTable({data:data,action:{addSerie:"Add this manga"}})
}
}
async function loadGroups(){
mikan.tableData = (await fetchApiData({type:"knowngroups"}))["data"].map(e=>({tgroupid:e.tgroupid,name:e.name,ignore:Boolean(e.ignore).toString(),fake:Boolean(e.fake).toString(),deleted:Boolean(e.deleted).toString()})).map(e=>{e["action"]=[
	{
		name:"Mark group properties",
		func: async ()=>{
			log("tableAction act:"+"markgroupproperties",true);
			const markValue = await formWindow({title:"Group properties",form:[{id:"ignore",name:"ignore",type:"checkbox",value:e["ignore"]=="true"?true:false},{id:"fake",name:"fake",type:"checkbox",value:e["fake"]=="true"?true:false},{id:"deleted",name:"deleted",type:"checkbox",value:e["deleted"]=="true"?true:false}]});
			if(markValue["status"]=="success"){await fetchApiData({requestType:"post",type:"knowngroupsset",valueObj:{id:e["tgroupid"],ignore:markValue["data"]["ignore"],fake:markValue["data"]["fake"],deleted:markValue["data"]["deleted"]}})}
			checkPage()
		}
	},
];return e});
displayTable({data:mikan.tableData,action:{markgroupignore:"Mark ignore group data",markgroupfake:"Mark fake group data",markgroupdeleted:"Mark deleted group data"}})
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
const logEleChild=logEle.childNodes;
if(logEleChild.length>0){
logEle.insertBefore(txt,logEleChild[0]);
}else{
logEle.append(txt);
}
logEle.scrollTop = 0;
}
}
async function showSettings(){
let data = (await fetchApiData({type:"getsettings"}))["data"];
data.forEach(e=>{
	let v=e.value;
	e.value=document.createElement("input");
	e.value.value=v;
})
let save=document.createElement("button");
save.addEventListener("click",saveSettings);
save.innerHTML="Save";
data.push({id:"saveSetting",name:"Save Settings",value:save});
displayTable({data:data})
}
async function saveSettings(){
const url = new URL(location);
if("settings"==url.searchParams.get("page")){
	let list=document.querySelectorAll("#content [data-id]:not([data-id=saveSetting]) input");
	let data=[];
	for (let i = 0; i < list.length; i++){
		data.push({id:list[i].parentNode.dataset.id,value:list[i].value})
	}
	fetchApiData({type:"setsettings",valueObj:{type:"setsettings",value:JSON.stringify(data)}});
	log("save settings: "+JSON.stringify(data),true)
}
}
async function showProgress(){
let progress = mikan.progress;
let progressAll = progress["update"];
let progressNo = progress["updateNo"];
if(history.state != null && history.state.page == "progress"){
	let t = document.querySelector("#content");
	for(let i=0;i<10;i++) {
		let pInfo = structuredClone(progressAll[mikan.progress.updateNo[i]]);
		let tEle = t.querySelectorAll("[data-id='"+mikan.progress.updateNo[i]+"']");
		if(tEle.length>1){
			pInfo["status"] = pInfo["statusText"];
			pInfo["serieid"] = pInfo["parent"];
			delete pInfo["statusText"];
			delete pInfo["parent"];
			const progressCol = ["progress","subprogress"];
			for(let col=0; col<tEle.length; col++){
				let dataCol = tEle[col].dataset.cols;
				if(progressCol.includes(dataCol)){
					let t;
					try{t = pInfo[dataCol].innerText!=undefined ? pInfo[dataCol].innerText : pInfo[dataCol]+"%"}
					catch{pInfo[dataCol]+"%"}
					tEle[col].title = t;
					tEle[col].colsdata = t;
					let pCon = tEle[col].childNodes[0].childNodes[0];
					pCon.innerHTML = t;
					pCon.style.width = t;
				}else{
					tEle[col].title = pInfo[dataCol];
					tEle[col].colsdata = pInfo[dataCol];
					tEle[col].innerHTML = pInfo[dataCol];
				}
			}
		} else{
			let data = [];
			Object.keys(progressAll).forEach(e=>{
				let ptmp = structuredClone(progressAll[e]);
				ptmp["status"] = ptmp["statusText"];
				ptmp["serieid"] = ptmp["parent"];
				delete ptmp["statusText"];
				delete ptmp["parent"];
				const progressCol = ["progress","subprogress"];
				progressCol.forEach(pro=>{
					const pCon = document.createElement("div");
					const p = document.createElement("div");
					pCon.classList.add("progressCon");
					p.classList.add("progress");
					let t;
					try{t = ptmp[pro].innerText!=undefined ? ptmp[pro].innerText : ptmp[pro]+"%"}
					catch{ptmp[pro]+"%"}
					p.style.width = t;
					p.innerHTML = t;
					pCon.append(p);
					ptmp[pro] = pCon;
				})
				ptmp["action"] = [
					{
						name:"Start queue",
						func: ()=>{
							log("tableAction act:"+"processqueue",true);
							fetchApiData({type:"processqueue"})
						}
					},
					{
						name:"Stop queue",
						func: ()=>{
							log("tableAction act:"+"stopqueue",true);
							fetchApiData({type:"stopqueue"})
						}
					},
					{
						name:"Restart failed queue",
						func: ()=>{
							log("tableAction act:"+"processfailedqueue",true);
							fetchApiData({type:"processfailedqueue"})
						}
					},
					{
						name:"Clear done queue",
						func: ()=>{
							log("tableAction act:"+"cleardonequeue",true);
							fetchApiData({type:"cleardonequeue"})
						}
					},
					{
						name:"Clear queue",
						func: ()=>{
							log("tableAction act:"+"clearqueue",true);
							fetchApiData({type:"clearqueue"})
						}
					},
					{
						name:"Clear request cache",
						func: ()=>{
							log("tableAction act:"+"clearcache",true);
							fetchApiData({type:"clearcache"})
						}
					}
				]
				data.push(ptmp);
			})
			displayTable({data:data});
			break;
		}
	}
}
const bottomPrg = document.querySelector("#progress");
const bottomHH = bottomPrg.offsetHeight/2;
const bottomSc = bottomPrg.scrollTop;
progressNo.forEach(pro=>{
	if(bottomPrg.querySelectorAll("[data-id='"+pro+"']").length<1){
		const pCon = document.createElement("div");
		const p = document.createElement("div");
		pCon.classList.add("progressCon");
		p.classList.add("progress");
		pCon.dataset.id = pro;
		p.style.width = progressAll[pro]["subprogress"] + "%";
		p.innerHTML = progressAll[pro]["subprogress"] + "% " + progressAll[pro]["statusText"] + " | " + progressAll[pro]["name"];
		pCon.append(p);
		bottomPrg.append(pCon)
	}
})
let bottomPrgAll = bottomPrg.querySelectorAll("[data-id]");
for(let num=0;num<bottomPrgAll.length;num++){
	const prgid = bottomPrgAll[num].dataset.id;
	const ele = bottomPrgAll[num];
	if(!progressNo.includes(prgid)){
		ele.remove()
	}
	else if(prgid == progressNo[num]){
		const p=ele.querySelector(".progress");
		p.style.width = progressAll[prgid]["subprogress"] + "%";
		p.innerHTML = progressAll[prgid]["subprogress"] + "% " + progressAll[prgid]["statusText"] + " | " + progressAll[prgid]["name"];
	}
	else if(progressNo.includes(prgid)){
		const p=ele.querySelector(".progress");
		p.style.width = progressAll[prgid]["subprogress"] + "%";
		p.innerHTML = progressAll[prgid]["subprogress"] + "% " + progressAll[prgid]["statusText"] + " | " + progressAll[prgid]["name"];
		if(progressNo.indexOf(prgid)>0){bottomPrg.querySelector("[data-id='"+progressNo[progressNo.indexOf(prgid)-1]+"']").after(ele)}
		else(bottomPrg.insertAdjacentElement("afterbegin",ele))
	}
}
if(bottomSc<bottomHH){bottomPrg.scrollTop=bottomSc}

if(progressNo.length > 0){bottomPrg.classList.remove("empty")}
else{bottomPrg.classList.add("empty")}
}
async function sortTableData(table){
let head = Object.keys(mikan.tableData["0"]).filter(e=>e.toLowerCase()!="action");
let sortOld = {};
let formSort = [];
for(let h=0;h<head.length;h++){
	formSort.push({
		id: head[h],
		type: "select",
		value: (mikan.sortLast.includes(head[h])&&mikan.sort[head[h]]=="desc") ? "desc,asc" : "asc,desc",
		name: head[h]
	})
	sortOld[head[h]] = (mikan.sortLast.includes(head[h])&&mikan.sort[head[h]]=="desc") ? "desc" : "asc";
}
let form = await formWindow({
	title: "Sort by",
	id: "sortdata",
	form: formSort
});
if(form["status"]=="success"){
	const data = form["data"];
	for(let h=0; h<head.length; h++){
		if(data[head[h]]!=sortOld[head[h]]){
			if(mikan.sortLast.includes(head[h])){mikan.sortLast.splice(mikan.sortLast.indexOf(head[h]),1)}
			mikan.sortLast.unshift(head[h]);
			mikan.sort[head[h]]=data[head[h]];
			displayTable(table);
		}
	}
}
}
async function filterTableData(){
const head = Object.keys(mikan.tableData[0]).filter(e=>e.toLowerCase()!="action");
const filterListOld = Object.keys(mikan.filterList);
const key = [];
const cols = [];
for(let v of head){
	if(v.includes("provider")){key.push(v);cols.push(v)}
	else if(v.includes("id")){key.push(v)}
	else{cols.push(v)}
}
const dataList = document.querySelectorAll("#content > .data > *");
let formFilter = [];
for(let h=0;h<head.length;h++){
	formFilter.push({
		id: head[h],
		type: "text",
		value: filterListOld.includes(head[h]) ? mikan.filterList[head[h]] : "",
		name: head[h]
	})
}
let form = await formWindow({
	title: "Filter",
	id: "filterdata",
	form: formFilter
});
if(form["status"]=="success"){
	const data = Object.fromEntries(Object.entries(form["data"]).filter(([, v]) => v!==""));
	mikan.filterList = data;
	const filterList = Object.keys(data);
	let rowIn = [];
	for(let d=0;d<dataList.length;d++){
		if(filterList.length<1){dataList[d].classList.remove("filterHide");continue;}
		for(let f=0;f<filterList.length;f++){
			const re = new RegExp(data[filterList[f]],"i");
			if(key.includes(filterList[f])&&dataList[d].dataset[filterList[f]].search(re)>=0&&dataList[d].dataset.cols==cols[0]){
				dataList[d].parentNode.querySelectorAll("[data-row='"+dataList[d].dataset["row"]+"']").forEach(e=>{e.classList.remove("filterHide")});
				rowIn.push(dataList[d].dataset["row"]);
			}
			else if(cols.includes(filterList[f])&&dataList[d].dataset.colsdata.search(re)>=0&&dataList[d].dataset.cols==filterList[f]){
				dataList[d].parentNode.querySelectorAll("[data-row='"+dataList[d].dataset["row"]+"']").forEach(e=>{e.classList.remove("filterHide")});
				rowIn.push(dataList[d].dataset["row"]);
			}
			else if(!(rowIn.includes(dataList[d].dataset.row))){dataList[d].classList.add("filterHide");}
		}
	}
} else{
	mikan.filterList = {};
	dataList.forEach(e=>e.classList.remove("filterHide"));
}
}
async function searchTableData(value){
if(value!=""){
	const head = Object.keys(mikan.tableData[0]).filter(e=>e.toLowerCase()!="action");
	const key = [];
	const cols = [];
	for(let v of head){
		if(v.includes("provider")){key.push(v);cols.push(v)}
		else if(v.includes("id")){key.push(v)}
		else{cols.push(v)}
	}
	const dataList = document.querySelectorAll("#content > .data > *");
	const data = value;
	const filterList = head;
	let rowIn = [];
	for(let d=0;d<dataList.length;d++){
		if(filterList.length<1){dataList[d].classList.remove("searchHide");continue;}
		for(let f=0;f<filterList.length;f++){
			const re = new RegExp(data,"i");
			if(key.includes(filterList[f])&&dataList[d].dataset[filterList[f]].search(re)>=0&&dataList[d].dataset.cols==cols[0]){
				dataList[d].parentNode.querySelectorAll("[data-row='"+dataList[d].dataset["row"]+"']").forEach(e=>{e.classList.remove("searchHide")});
				rowIn.push(dataList[d].dataset["row"]);
			}
			else if(cols.includes(filterList[f])&&dataList[d].dataset.colsdata.search(re)>=0&&dataList[d].dataset.cols==filterList[f]){
				dataList[d].parentNode.querySelectorAll("[data-row='"+dataList[d].dataset["row"]+"']").forEach(e=>{e.classList.remove("searchHide")});
				rowIn.push(dataList[d].dataset["row"]);
			}
			else if(!(rowIn.includes(dataList[d].dataset.row))){dataList[d].classList.add("searchHide");}
		}
	}
} else{
	document.querySelectorAll("#content > .data > *").forEach(e=>e.classList.remove("searchHide"));
}
}
async function contextMenu(arg){
let def = {
	id: "",
	title: "",
	location: document.body,
	x:0,
	y:0,
	event:{},
	context:{
		"id":{
			name: "text",
			action: ()=>{}
		}
	}
};
let out = {status:"", data:{}}
let checkInput = checkArg({
	input:arg,
	context:[
		{var:"id", type:"string", def:"context"},
		{var:"title", type:"string", },
		{var:"location", type:"object", def:document.body},
		{var:"x", type:"number"},
		{var:"y", type:"number"},
		{var:"event", type:"object"},
		{var:"context", type:"object"}
	]
});
if(checkInput["status"]=="failed"){
	throw new Error(checkInput["data"]["msg"]);
}
arg=checkInput["data"]["normal"];
const body = document.body;
const con = document.querySelector("#context");
const all = con.querySelectorAll("*");
const oldId = con.querySelectorAll("[data-context-id='"+arg["id"]+"']")
if(oldId.length>0){oldId.forEach(e=>con.removeChild(e));return}
try{all.forEach(e=>e.rm())}catch{}
let yPerc,xPerc;
if(arg["event"]!={} && "type" in arg["event"] && arg["event"].type == "contextmenu"){
arg["event"].preventDefault();
yPerc = arg["event"].offsetY/arg["location"].scrollHeight;
xPerc = arg["event"].offsetX/arg["location"].scrollWidth;
}

const contextCon = document.createElement("div");
contextCon.classList.add("context","loading");
con.append(contextCon);
contextCon.tabIndex=0;
contextCon.dataset.contextId = arg["id"];
let topC = arg["location"].getBoundingClientRect().y+arg["location"].offsetHeight+arg["y"];
let leftC = arg["location"].getBoundingClientRect().x+arg["location"].offsetWidth+arg["x"];
let relocation = ()=>{
if(arg["event"]!={} && "type" in arg["event"] && arg["event"].type == "contextmenu"){
topC = (yPerc*arg["location"].scrollHeight)+arg["location"].getBoundingClientRect().y+arg["y"]
leftC = (xPerc*arg["location"].scrollWidth)+arg["location"].getBoundingClientRect().x+arg["x"]
}
contextCon.style.top = (body.offsetHeight > topC+contextCon.offsetHeight ? topC : topC-(contextCon.offsetHeight))+"px";
contextCon.style.left = (body.offsetWidth > leftC+contextCon.offsetWidth ? leftC : leftC-(contextCon.offsetWidth))+"px";
contextCon.style.maxHeight = "min("+body.offsetHeight+"px,20rem)";
contextCon.style.maxWidth = "min("+body.offsetWidth+"px,20rem)";

if(contextCon.classList.contains("loading")){contextCon.classList.remove("loading")}
};

window.addEventListener("resize",relocation);
setTimeout(relocation,1)

let parentSc = (el)=>{
	if(el!=body){
		el.parentNode.addEventListener("scroll",relocation);
		if(el.parentNode!=body){parentSc(el.parentNode)}
	}
}
let parentScRm = (el)=>{
	if(el!=body && !(el.parentNode===null)){
		el.parentNode.removeEventListener("scroll",relocation);
		if(el.parentNode!=body){parentScRm(el.parentNode)}
	}
}
parentSc(arg["location"]);

const elementLocationCheck = new MutationObserver(() => {if(!arg["location"].isConnected){reEvt()}});
const reEvt = ()=>{
if(contextCon.isConnected){
con.removeChild(contextCon);
window.removeEventListener("resize",relocation);
contextCon.removeEventListener("mouseleave",reEvt);
parentScRm(arg["location"]);
elementLocationCheck.disconnect();
}
}
elementLocationCheck.observe(body, {childList:true, subtree:true});

contextCon.rm = reEvt;

for(const c in arg["context"]){
const context = document.createElement("button");
context.innerHTML = arg["context"][c]["name"];
context.tabIndex = 1;
context.addEventListener("click",()=>{reEvt();arg["context"][c]["action"]()});
context.addEventListener("mouseenter",context.focus);
contextCon.append(context);
}
const contextClose = document.createElement("button");
contextClose.innerHTML = "Close menu";
contextClose.tabIndex = 1;
contextClose.addEventListener("click",reEvt);
contextClose.addEventListener("mouseenter",contextClose.focus);
contextCon.append(contextClose);

contextCon.querySelector("*").focus();
contextCon.addEventListener("mouseleave",reEvt);
}
function checkArg(arg){
let data = {
	input: {},
	context: [
		{
			var: "text",
			type: "string",
			def: "default",
			req: false
		}
	]
}
let out = {status:"", data:{}}
let err = (r)=>{out["status"] = "failed";out["data"]["msg"] = r;return out};
let suc = (r,d)=>{out["status"] = "success";out["data"]["msg"] = r;out["data"]["normal"] = d;return out};

if(typeof arg != "object"){return err("[checkArg] function argument not object")}
if(!("input" in arg && "context" in arg)){return err("[checkArg] input or context not in argument")}
if(!(Array.isArray(arg["context"]))){return err("[checkArg] context not an array")}
if(typeof arg["input"]!="object"){arg["input"]={}}

let input = arg["input"];
let context = arg["context"];

for(let i=0; i<context.length; i++){
	let v = context[i];
	if(typeof v!="object"){return err("[checkArg] value include context is not a object")}
	if(!("var" in v && "type" in v)){return err("[checkArg] value include context is not complete")}
	
	v["type"] = v["type"].toLowerCase();
	v["req"] = "req" in v ? Boolean(v["req"]) : false;
	if(typeof input[v["var"]]!=v["type"]&&v["type"]!="array"&&!(typeof input[v["var"]]=="undefined"&&!(v["req"]))){
		return err(`"${v["var"]}" is wrong type (require ${v["type"]} but received ${typeof input[v["var"]]})`)
	}
	if(!(Array.isArray(input[v["var"]]))&&v["type"]=="array"&&!(typeof input[v["var"]]=="undefined"&&!(v["req"]))){
		return err(`"${v["var"]}" is wrong type (require ${v["type"]} but received ${typeof input[v["var"]]})`)
	}
	if(v["req"]){
		if(!(v["var"] in input)){
			return err(`"${v["var"]}" is require`)
		}
		if(v["type"]=="array"&&!(input[v["var"]].length>0)){
			return err(`"${v["var"]}" is require but received emply array`)
		}
		if(v["type"]=="object"&&Object.keys(input[v["var"]]).length<0){
			return err(`"${v["var"]}" is require but received emply object`)
		}
		if(v["type"]=="string"&&input[v["var"]]==""){
			return err(`"${v["var"]}" is require but received emply string`)
		}
		if(v["type"]=="number"&&isNaN(input[v["var"]])){
			return err(`"${v["var"]}" is require but received NaN (Not a Number)`)
		}
	}
	if(typeof input[v["var"]]=="undefined"){
		if(v["type"]=="array"){
			if(Array.isArray(v["def"])){input[v["var"]]=v["def"]}
			else{input[v["var"]] = []}
		}
		if(v["type"]=="object"){
			if(typeof v["def"] == "object"){input[v["var"]]=v["def"]}
			else{input[v["var"]] = {}}
		}
		if(v["type"]=="string"){
			if(typeof v["def"] == "string"){input[v["var"]]=v["def"]}
			else{input[v["var"]] = ""}
		}
		if(v["type"]=="number"){
			if(typeof v["def"] == "number"){input[v["var"]]=v["def"]}
			else{input[v["var"]] = 0}
		}
		if(v["type"]=="boolean"){
			if(typeof v["def"] == "boolean"){input[v["var"]]=v["def"]}
			else{input[v["var"]] = false}
		}
	}
}
return suc("[checkArg] sucess",input)
}



mikan = {
	"sort": {chapter:"asc",name:"asc"},
	"sortLast": ["chapter","name"],
	"filterList": {},
	"progress": {},
	"login": false,
	"debug": false,
	"server": window.location.origin,
	"moreAction": {
		"restartserver": {name:"Restart Server", action:()=>{fetchApiData({type:"restart"})}},
		"stopserver": {name:"Stop Server", action:()=>{fetchApiData({type:"stop"})}}
	},
	"moreActionDef": {
		"restartserver": {name:"Restart Server", action:()=>{fetchApiData({type:"restart"})}},
		"stopserver": {name:"Stop Server", action:()=>{fetchApiData({type:"stop"})}}
	},
};
load1st = ()=>{
	loadToken()
	checkPage()
	serverEvent()
}
checklogin1st = async() => {
	try{
		if(localStorage.getItem("token")!=null) {
			let r = await fetch(mikan["server"]+'/api?type=ping', {
			headers: {'Authorization': `Bearer ${JSON.parse(localStorage.getItem("token"))}`}
			});
			if(r.status == 200){mikan.login = true; load1st(); document.querySelector(".loginlogout").classList.add("login")}
			else if(r.status == 401){log("Login token not valid, Please try login again."); document.querySelector("#login").click()}
			else{log("Cannot connect to server.")}
		}
	}catch{
		log("Login token corrupt, Please try login again.")
		document.querySelector("#login").click();
	}
};

document.querySelector("header > #menuToggle").addEventListener("click", () => {
	document.querySelector("#container > .left").classList.toggle("hide");
});
document.querySelectorAll("nav > button").forEach(n => {
	const url = new URL(location);
	url.searchParams.set("page", n.value);
	url.searchParams.set("value", "");
	n.addEventListener("click",()=>{history.pushState({page:n.value,value:""}, "", url);checkPage()})
});
document.querySelector("#more").addEventListener("click", async () => {
	contextMenu({id:"more",location:document.querySelector("#more"),context:mikan.moreAction})
});
document.querySelector("#login").addEventListener("click", async () => {
	const info = await formWindow({title:"Login", form:[{id:"username",type:"text",name:"username"},{id:"password",type:"password",name:"password"}]})
	if(info["status"]=="success"){
		login({username:info["data"]["username"],password:info["data"]["password"]},)
	}
});
document.querySelector("#logout").addEventListener("click", logout);
window.addEventListener('popstate', checkPage);
log("script loaded");
checklogin1st();