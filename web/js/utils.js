import { checkArg } from "./checkarg.js";
/**
 * @param {{searchEnable?: boolean, sortEnable?: boolean, filterEnable?: boolean, searchLink?: Function, sortList?: any[], sortReturn?: Function, filterList?: any[], filterReturn?: Function}} arg
 * @returns {Promise<void>}
 */
export async function updateContentBar(arg){
let check = checkArg({input:arg,context:[
    {
        type:"boolean",
        var:"searchEnable",
		req:false,
    },
    {
        type:"boolean",
        var:"sortEnable",
		req:false,
    },
    {
        type:"boolean",
        var:"filterEnable",
		req:false,
    },
    {
        type:"function",
        var:"searchLink",
		req:false,
    },
    {
        type:"array",
        var:"sortList",
		req:false,
    },
    {
        type:"function",
        var:"sortReturn",
		req:false,
    },
    {
        type:"array",
        var:"filterList",
		req:false,
    },
    {
        type:"function",
        var:"filterReturn",
		req:false,
    },
]});
if(check["status"]=="failed"){
	throw new Error(check["data"]["msg"]);
}

const normal = check["data"]["normal"];
const contentBar = document.querySelector("#contentBar");
const searchBar = contentBar.querySelector("#searchdata");
const sortButton = contentBar.querySelector("#sort");
const filterButton = contentBar.querySelector("#filter");

if("searchEnable" in arg){
	if(normal["searchEnable"]){
		searchBar.style.display = "";
	}else{
		searchBar.style.display = "none";
	}
}
if("sortEnable" in arg){
	if(normal["sortEnable"]){
		sortButton.style.display = "";
	}else{
		sortButton.style.display = "none";
	}
}
if("filterEnable" in arg){
	if(normal["sortEnable"]){
		filterButton.style.display = "";
	}else{
		filterButton.style.display = "none";
	}
}
if(searchBar.style.display == "none" && sortButton.style.display == "none" && filterButton.style.display == "none"){
	contentBar.style.display = "none";
}else{
	contentBar.style.display = "";
}
if("searchLink" in arg){
	searchBar.value = "";
	searchBar.oninput = (e)=>{normal["searchLink"](e.target.value)};
}
if("sortList" in arg){
	const sortList = normal["sortList"];
	let sortForm = [];
	let sortOld = {};
	sortList.forEach(s=>{
		sortForm.push({
			id: s,
			type: "select",
			value: (mikan.sortLast.includes(s) && mikan.sort[s] == "desc") ? "desc,asc" : "asc,desc",
			name: s
		})
		sortOld[s] = (mikan.sortLast.includes(s) && mikan.sort[s] == "desc") ? "desc" : "asc";
	});

	sortButton.onclick = async()=>{
		let form = await formWindow({
			title: "Sort by",
			id: "sortdata",
			form: sortForm
		});

		if(form["status"] == "success"){
			const data = form["data"];

			sortList.forEach(s=>{
				if(data[s] != sortOld[s]){
					if(mikan.sortLast.includes(s)){mikan.sortLast.splice(mikan.sortLast.indexOf(s),1)}
					mikan.sortLast.unshift(s);
					mikan.sort[s] = data[s];
				}
			})
			sortButton.linkFunction({sort:mikan.sort,sortLast:mikan.sortLast})
		}
	}
}
if("sortReturn" in arg){
	sortButton.linkFunction = (e)=>{normal["sortReturn"](e)};
}
if("filterList" in arg){
	const filterList = normal["filterList"];
	mikan.filterList = {};

	filterButton.onclick = async()=>{
		let filterListOld = Object.keys(mikan.filterList);
		let filterForm = [];
		
		filterList.forEach(f=>{
			filterForm.push({
				id: f,
				type: "text",
				value: filterListOld.includes(f) ? mikan.filterList[f] : "",
				name: f
			})
		});

		let form = await formWindow({
			title: "Filter",
			id: "filterdata",
			form: filterForm
		});

		if(form["status"] == "success"){
			const data = form["data"];
			mikan.filterList = data;
			filterButton.linkFunction({filterList:data})
		}
	}
}
if("filterReturn" in arg){
	filterButton.linkFunction = (e)=>{normal["filterReturn"](e)};
}
}

/**
 * @typedef {
 * "button" | "checkbox" | "color" | "date" | "email" | "file" | 
 * "number" | "password" | "range" | "search" | "text" | "url" |
 * "select"} formInputType
 * 
 * @template {readonly {
 * id: string, type: formInputType, value?: string,
 * name: string, disable?: boolean}[]} const F
 * 
 * @param {{id?: string, location?: HTMLElement, title?: string, form: F}} arg
 * @returns {Promise<{status: string, data: any}>}
 */
export async function formWindow(arg){
let checkInput = checkArg({
	input:arg,
	context:[
		{var:"id", type:"string", def:"formWindow"},
		{var:"location", type:"element", def:(document.body)},
		{var:"title", type:"string"},
		{var:"form", type:"array", req:true}
	]
});
if(checkInput["status"]=="failed"){
	throw new Error(checkInput["data"]["msg"]);
}
arg=checkInput["data"]["normal"];
let out = {status:"", data:{}};
const formEle = document.querySelector("#form");

formEle.querySelectorAll(".formContainer.form[data-id='"+arg["id"]+"']").forEach(e=>e.cancel());

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
formEle.append(form);

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

export function formWindowInit(){
const formEle = document.querySelector("#form");
formEle.addEventListener("click", (e) => {
	if(e.target !== e.currentTarget){return}
	formEle.querySelectorAll(".formContainer.form[data-id]").forEach(e=>e.cancel());
	formEle.innerHTML="";
});
const observer = new MutationObserver((mutationList, observer) => {
	mutationList.forEach((mutation) => {
		if(mutation.addedNodes.length > 0){
			formEle.classList.add("active")
		}
		if(mutation.removedNodes.length > 0 && mutation.target.childNodes.length<1){
			formEle.classList.remove("active")
		}
	});
});
observer.observe(formEle,{childList: true});
}

/**
 * @typedef {"get" | "post"} requestType
 * 
 * @param {{type: string, valueObj?: object, requestType?: requestType}} arg
 * @returns {Promise<unknown | undefined>}
 */
export async function fetchApiData(arg) {
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

/**
 * @param {value: any, trance?: boolean}
 * @returns {void}
 */
export async function log(value,trance=false){
if((trance==true && mikan.debug==true) || trance==false){
	const date = new Date();
	const dateFormat = date.toISOString().slice(0, 10)+" "+date.toTimeString().slice(0,8);
	value = "["+dateFormat+"] "+value;
	console.log(value);
	const txt = document.createElement("p");
	txt.innerHTML=value.toString();
	const logEle = document.querySelector("#log>div:nth-child(2)");
	const logEleChild = logEle.childNodes;
if(logEleChild.length>0){
	logEle.insertBefore(txt,logEleChild[0]);
}else{
	logEle.append(txt);
}
logEle.scrollTop = 0;
}
}