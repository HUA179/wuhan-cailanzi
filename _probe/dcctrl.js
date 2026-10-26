$(function(){
    initLeftMenu(); // 初始化左侧菜单
    $("#riduDate").val(yesterdayYmd()); // 初始化日度数据搜索时间
});

function initLeftMenu() {
    var currentUrl = window.location.href;
    var urlParam = "";
    if(currentUrl && (currentUrl.indexOf("?") != -1)){
        urlParam = currentUrl.split("?")[1];
        if (urlParam) {
            changeClickStyle(urlParam);
            if(urlParam == 'jgnfcprd'){
                load_ridu_data(urlParam); 	// 日度监测数据
            } else if(urlParam.indexOf('jgnfcpzd')!=-1){
                load_zhoudu_data(urlParam); // 周度监测数据
            } else if(urlParam.indexOf('jgsczlzdjc')!=-1){
                load_qita_data(urlParam); // 周度监测数据 - 生产资料
            } else if(urlParam.indexOf('scsjnfcp')!=-1) {
                load_qita_data('scsjnfcp');
            } else if(urlParam.indexOf('qcxfqk')!=-1) {
                load_news('qcxfqk');
            }  else if(urlParam.indexOf('shxfplsze')!=-1) {
                load_new_data('shxfplsze');
            }  else if(urlParam.indexOf('gnsczz')!=-1) {
                load_new_data('gnsczz');
            }  else if(urlParam.indexOf('scsjgyxfp')!=-1) {
                load_qita_data('scsjgyxfp');
            }   else if(urlParam.indexOf('jgsczlzdjc')!=-1) {
                load_qita_data('jgsczlzdjc');
            } else {
                changeClickStyle("jgnfcprd");
                load_ridu_data("jgnfcprd");
            }
        } else {
            changeClickStyle("jgnfcprd");
            load_ridu_data("jgnfcprd");
        }
    } else {
        changeClickStyle("jgnfcprd");
        load_ridu_data("jgnfcprd");
    }
}

// 左测菜单选中样式控制
function changeClickStyle(element){
    $("a[id^='li_']").removeAttr("style","");
    $("#li_"+element).css("background-color","#046eb8");
    $("#li_"+element).css("color","#fff");
}

/**
 * ===========================日度监测数据相关 Start==================================
 */

// 农副产品-日度监测数据 - 数据加载
function load_ridu_data(urlParam){
    changeClickStyle(urlParam);
    showOrHideContainer(1);
    getEnterpriseList('210010'); // 粮油 - 粳米（默认）
}

// 日度数据企业列表展示（根据产品cate_id）
function getEnterpriseList(cate_id){
    if(cate_id == '210010') {
        $(".select-items .num").html("粮油");
        $("#categorySeled").html("粳米");
    }
    $.ajax({
        type : "POST",
        url : "/cif/getEnterpriseByCateId2019.fhtml",
        data : {
            cateId:cate_id
        },
        success : function(json) {
            var datas = json.datas;
            var html = "";
            if(datas && datas.length > 0 ){
                //$(".select-items #categorySeled").html(datas[0].COMMDITYNAME);
                // drawChartRdH(datas); // 环状图Echart
                drawChartRdZZ(datas); // 柱状折线Echart
                for(var i=0; i<datas.length; i++){
                    html += "<tr><td width='120'>"+datas[i].COUNTY_NAME+"</td>" +
                        "<td width='480'>"+datas[i].NAME+"</td>" +
                        "<td width='80'>"+datas[i].PRICE2+"</td>" +
                        "<td width='80'>"+datas[i].PRICE1+"</td>" +
                        "<td width='60'>"+datas[i].PRICE3+"%</td>" +
                        "<td style='cursor:pointer' onclick='enterpriseCateChart("+datas[i].ENTERID+","+datas[i].COMMDITY_ID+");'><i class='data-icon'></i></td></tr>";
                }
            } else {
                html = "暂无数据";
            }
            $("#table_riqy").html(html);
        }
    });
}

// 日度数据单品种走势图
function enterpriseCateChart(ent_id, cate_id){
    $.ajax({
        type : "POST",
        url : "/cif/enterpriseCateChart.fhtml",
        data : {
            entId: ent_id,
            cateId: cate_id
        },
        success : function(json) {
            var datas = json.datas;
            // 折线图（价格走势）
            var dateArr = new Array();
            var priceArr = new Array();
            for (var i = 0; i < datas.length; i++) {
                dateArr[i] = datas[i].RPTDATE;
                priceArr[i] = datas[i].PRICE;
            }
            $("#title1").val(json.title);
            $("#dateArr1").val(dateArr);
            $("#priceArr1").val(priceArr);
            var dateArrMinTime = dateArr ? dateArr[0] : this.getCurrentDateYmd();
            $("#dateArrMinTime").val(dateArrMinTime);
            drawChartRdInfo(json.title, dateArr, priceArr, false);

            var table_html = "";
            for(var i=datas.length-1; i>=0; i--){
                table_html += "<tr><td  width='200'>"+datas[i].RPTDATE+"</td>" +
                    "<td width='200'>"+datas[i].PRICE+"</td>" +
                    "<td width='200'>"+datas[i].difference+"</td>" +
                    "<td>"+datas[i].trend+"</td></tr>";
            }
            $("#listRdInfo").html(table_html);
        }
    });
}

// 日度数据环状图
//function drawChartRdH(datas) {
//	if (datas && datas.length>0) {
//		var newDatas1 = datas.filter(function(data){
//			return data.PRICE3 > 0;
//		});
//		var newDatas2 = datas.filter(function(data){
//			return data.PRICE3 == 0;
//		});
//		var newDatas3 = datas.filter(function(data){
//			return data.PRICE3 < 0;
//		});
//
//		var len1 = newDatas1.length;
//		var len2 = newDatas2.length;
//		var len3 = newDatas3.length;
//
//		var rbHData = [];
//
//		if(len1>0) {
//			rbHData.push({ value: len1, name: '上涨' });
//		}
//
//		if(len2>0) {
//			rbHData.push({ value: len2, name: '持平' });
//		}
//
//		if(len3>0) {
//			rbHData.push({ value: len3, name: '下降' });
//		}
//
//		var rdHtitle = "各批发市场"+datas[0].COMMDITYNAME+"价格涨跌分";
//		var optionRdH = {
//	        color: ["#FAC858", "#9FE080", "#73C0DE"],
//	        title: {
//	            text: rdHtitle,
//	            left: 'center'
//	        },
//	        grid: {
//	            top: '25%',
//	            left: '4%',
//	            right: '4%',
//	            bottom: '8%',
//	            containLabel: true
//	        },
//	        tooltip: {
//	            trigger: 'item',
//	            formatter: '{b0}: {c0}家'
//	        },
//	        legend: {
//	            bottom: 0,
//	            left: 'center',
//	            data: ["上涨", "持平", "下降"]
//	        },
//	        series: [
//	            {
//	                name: '',
//	                type: 'pie',
//	                radius: ['30%', '70%'],
//	                data: rbHData,
//	                label: {
//	                    formatter: '{b0}{d}%',
//	                    show: true,
//	                    distance: 0,
//	                    color: "#000",
//	                    rotate: 0,
//	                    align: 'left',
//	                    //position: 'inside',
//	                    width: 15,
//	                },
//           labelLine: {
//	                    show: true,
//	                    length:3,
//	                },
//
//	            }
//	        ]
//	    };
//
//		_chartPieRdH = new drawCharts({ elem: 'mapBox2', option: optionRdH, theme: null }).init();
//	}
//}

// 日度数据柱状图+折线图
function drawChartRdZZ(datas) {
    datas.sort(function(a,b){
        return  b.PRICE2 - a.PRICE2;
    });
    var rdZZtitle = "全国各地批发市场"+datas[0].COMMDITYNAME+"价格排序";
    var compNameArr = [];
    var compDataArr = [];
    for(var i = 0; i< 15; i++) {
        var dataObj = datas[i];
//		compNameArr.push(dataObj.NAME.length>5 ? dataObj.NAME.substring(0,5)+"..." : dataObj.NAME );
        compNameArr.push(dataObj.NAME);
        compDataArr.push(dataObj.PRICE2);
    }

    var optionRdZZ1 = {
        color: ["#5470c6"],
        grid: {
            top: '25%',
            left: '4%',
            right: '4%',
            bottom: '8%',
            containLabel: true
        },
        legend: {
            data: ['日价格'],
            bottom: 0
        },
        tooltip: {
            trigger: 'axis'
        },
        title: {
            text: rdZZtitle,
            left: 'center',
            top: 30
        },
        toolbox: {
            show: true,
            feature: {
                magicType: { type: ['line', 'bar'] },
            },
            right: 40,
            top: 40
        },
        xAxis: {
            type: 'category',
            data: compNameArr,
            axisLabel: {
                interval: 0,
                rotate: 40,
                formatter : function(params){
                    return params.substring(0,6)+"...";
                }
            }
        },
        yAxis: {
            name: "元/公斤",
            type: 'value',
            "axisLine": {       //y轴
                "show": false
            },
            "axisTick": {       //y轴刻度线
                "show": false
            }
        },
        series: [
            {
                name: '日价格',
                type: 'bar',
                data: compDataArr,
            }
        ]
    };

    _chartPieRdZZ1 = new drawCharts({ elem: 'mapBox1', option: optionRdZZ1, theme: null }).init();
}

// 日度数据单品种折线图echart
function drawChartRdInfo(title, dateArr, priceArr, isSearch) {
    var newDateArr;
    var newPriceArr;
    if(dateArr && dateArr.length>15 && isSearch == false) {
        newDateArr = dateArr.slice(dateArr.length - 15);
        newPriceArr = priceArr.slice(priceArr.length - 15);
    } else {
        newDateArr = dateArr;
        newPriceArr = priceArr;
    }


    $("#minTime").val($("#dateArrMinTime").val());
    $("#startDate1").val(newDateArr[0]);
    $("#endDate1").val(newDateArr[newDateArr.length-1]);

    $("#container1").hide();
    $("#container2").hide();
    $("#container3").show();

    var optionRdInfo = {
        color: ["#5470c6"],
        grid: {
            top: '25%',
            left: '4%',
            right: '4%',
            bottom: '3%',
            containLabel: true
        },
        tooltip: {
            trigger: 'axis'
        },
        title: {
            text: title + "（单位：元/公斤）",
            left: 'center',
            top: 30
        },
        toolbox: {
            show: true,
            feature: {
                magicType: { type: ['line', 'bar'] },
            },
            right: 40,
            top: 40
        },

        xAxis: {
            type: 'category',
            boundaryGap: false,
            data: newDateArr,
            axisLabel: {
                interval: 0,
                rotate: 40
            }
        },
        yAxis: {
            type: 'value',
            axisLabel: {
                formatter: '{value} '
            }
        },
        series: [
            {
                // name: 'Highest',
                type: 'line',
                data: newPriceArr, // priceArr
                markPoint: {
                    data: [
                        { type: 'max', name: 'Max' },
                        { type: 'min', name: 'Min' }
                    ]
                },
                stack: 'a',
                areaStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        {
                            offset: 0,
                            color: 'rgba(84,112,198,0.8)'
                        },
                        {
                            offset: 1,
                            color: 'rgba(84,112,198,0.3)'
                        }
                    ])
                },
            }
        ]
    };

    _chartPieRdInfo = new drawCharts({ elem: 'mapBoxRdInfo', option: optionRdInfo, theme: null }).init();
}

// 按日期搜索日度数据单品种价格数据及echart折线图
function searchData1() {
    var startDate1 = $("#startDate1").val() ? $("#startDate1").val() : this.getCurrentDateYmd();
    var endDate1 = $("#endDate1").val() ? $("#endDate1").val() : this.getCurrentDateYmd();

    var start = new Date(startDate1.replace("-", "/").replace("-", "/"));
    var end = new Date(endDate1.replace("-", "/").replace("-", "/"));

    if(end<=start){
        alert("结束时间必须大于开始时间！");
        return false;
    }

    var startIndex = 0;
    var endIndex = 0;
    var title1 = $("#title1").val();
    var dateArr1 = $("#dateArr1").val().split(",");
    var priceArr1 = $("#priceArr1").val().split(",");
    var newDateArr1;
    var newPriceArr1;

    $.each(dateArr1,function(idx){
        if(dateArr1[idx] == startDate1){
            startIndex = idx;
        }
        if(dateArr1[idx] == endDate1){
            endIndex = idx;
        }
    });
    newDateArr1 = dateArr1.slice(startIndex, endIndex+1);
    newPriceArr1 = priceArr1.slice(startIndex, endIndex+1);
    this.drawChartRdInfo(title1, newDateArr1, newPriceArr1, true);
}

// 日度数据搜索
function searchRdData() {
    var riduCategory = $("#riduCategory").val() ? $("#riduCategory").val() : '210010';
    var riduDate = $("#riduDate").val() ?  $("#riduDate").val(): getCurrentDateYmd();
    $.ajax({
        type : "POST",
        url : "/cif/getEnterpriseListForDate.fhtml",
        data : {
            cateId: riduCategory,
            searchDate: riduDate
        },
        success : function(json) {
            var datas = json.datas;
            if(json.listRange && json.listRange == '0') {
                alert("超出查询时间范围，请重新选择！");
            }
            var html = "";
            if(datas && datas.length > 0 ){
                // drawChartRdH(datas); // 环状图Echart
                drawChartRdZZ(datas); // 柱状折线Echart
                for(var i=0; i<datas.length; i++){
                    html += "<tr><td width='120'>"+datas[i].COUNTY_NAME+"</td>" +
                        "<td width='480'>"+datas[i].NAME+"</td>" +
                        "<td width='80'>"+datas[i].PRICE2+"</td>" +
                        "<td width='80'>"+datas[i].PRICE1+"</td>" +
                        "<td width='60'>"+datas[i].PRICE3+"%</td>" +
                        "<td style='cursor:pointer' onclick='enterpriseCateChart("+datas[i].ENTERID+","+datas[i].COMMDITY_ID+");'><i class='data-icon'></i></td></tr>";
                }
            } else {
                html = "暂无数据";
            }
            $("#table_riqy").html(html);
        }
    });
}

/**
 * ===========================日度监测数据相关 End==============================
 */


/**
 * ===========================周度监测数据相关 Start============================
 */
// 加载周度数据
function load_zhoudu_data(urlParam){
    var type_index = "";
    if(urlParam.indexOf("_")!=-1){
        var type_arr = [];
        type_arr = urlParam.split("_");
        type_index = urlParam.slice(9);
        changeClickStyle(type_arr[0]);
    } else {
        type_index = "liangyou";
        changeClickStyle(urlParam);
    }

    showOrHideContainer(2);
    triggerZdBtn(type_index);
}

function loadList(indexIds, startDate, endDate, isSearch){
    // 532023 532029 532040 532048 532053
    $.ajax({
        type : "POST",
        url : "/cif/getWeekLineChart2021.fhtml",
        data : {
            indexIds: indexIds,
            startDate: startDate,
            endDate: endDate
        },
        success : function(resp) {
            if(resp && resp.length>0){
                // 获取数据开始时间和结束时间
                var resStartDate = resp[0].startDate;
                var resEndDate = resp[0].endDate;

                var dd = new Date();
                var yy = dd.getFullYear();
                var zdMinDate = (yy - 10) + resEndDate.slice(4);

                $("#zdMinDate").val(resStartDate);
                $("#zdStartDate").val(resStartDate);
                $("#zdEndDate").val(resEndDate);

                // 处理echart图
                handleZdEchart(resp, isSearch);
                // 处理table表格
                handleZdTable(resp);
            }
        }
    });
}

// 点击大类触发方法
function triggerZdBtn(type_index) {
    var zFlg = "";
    var curSelIndex = "";
    if(type_index && type_index.indexOf("_") != -1) {
        zFlg = type_index.split("_")[0];
        curSelIndex = type_index.split("_")[1];
    } else {
        zFlg = type_index;
    }
    // 获取子类，并渲染到页面
    var zdCategories = zhouduData.categoryDatas[zFlg];
    var zdCategoriesHtml = "";
    for(var i=0;i<zdCategories.length;i++) {
        zdCategoriesHtml += "<label><input type='checkbox' name='zdCateChks' title='"+zdCategories[i].name+"' value='"+zdCategories[i].id+"' onchange='handleZdCatesClick("+zdCategories[i].id+")'>"+zdCategories[i].name+"</label>";
    }
    $("#zdCategories").html(zdCategoriesHtml);

    // 根据分类加载默认数据

    if(zFlg == 'liangyou') {
        $("#zdjcCates").children(":first").addClass("on");
        $("#zdjcCates").children(":first").siblings().removeClass("on");
        curSelIndex = curSelIndex ? curSelIndex : "18055942";
    } else if(zFlg == 'roulei') {
        $("#zdjcCates").children().eq(1).addClass("on");
        $("#zdjcCates").children().eq(1).siblings().removeClass("on");
//		curSelIndex = "224049";
        curSelIndex = curSelIndex ? curSelIndex : "224049";
    } else if(zFlg == 'qindan') {
        $("#zdjcCates").children().eq(2).addClass("on");
        $("#zdjcCates").children().eq(2).siblings().removeClass("on");
        curSelIndex = curSelIndex ? curSelIndex : "22039920";
    } else if(zFlg == 'tangyan') {
        $("#zdjcCates").children().eq(3).addClass("on");
        $("#zdjcCates").children().eq(3).siblings().removeClass("on");
        curSelIndex = curSelIndex ? curSelIndex : "224055";
    }  else if(zFlg == 'shucai') {
        $("#zdjcCates").children().eq(4).addClass("on");
        $("#zdjcCates").children().eq(4).siblings().removeClass("on");
        curSelIndex = curSelIndex ? curSelIndex : "18055947";
    } else if(zFlg == 'shuiguo') {
        $("#zdjcCates").children().eq(5).addClass("on");
        $("#zdjcCates").children().eq(5).siblings().removeClass("on");
        curSelIndex = curSelIndex ? curSelIndex : "224089";
    } else if(zFlg == 'nailei') {
        $("#zdjcCates").children().eq(6).addClass("on");
        $("#zdjcCates").children().eq(6).siblings().removeClass("on");
        curSelIndex = curSelIndex ? curSelIndex : "532023";
    } else if(zFlg == 'shuichanpin') {
        $("#zdjcCates").children().eq(7).addClass("on");
        $("#zdjcCates").children().eq(7).siblings().removeClass("on");
        curSelIndex = curSelIndex ? curSelIndex : "224080";
    } else {
        $("#zdjcCates").children().eq(0).addClass("on");
        $("#zdjcCates").children().eq(0).siblings().removeClass("on");
        curSelIndex = curSelIndex ? curSelIndex : "18055942";
    }
    $("input[value="+curSelIndex+"]").attr('checked',true);
    loadList(curSelIndex, "", "", false);
}


// 点击子类触发方法
function handleZdCatesClick(clickIndex) {
    var indexIds = getCheckedCates();
    if(indexIds && indexIds.indexOf(",") > -1) {
        var indexIdsArr = indexIds.split(",");
        if(indexIdsArr.length > 3) {
            alert("最多选3个品种进行比对");
            $("input[value='"+clickIndex+"']").attr('checked',false);
            return false;
        }
    }
    loadList(indexIds, "", "", false);
}


// 组装echart datas 渲染ecahrt图
function handleZdEchart(resp, isSearch) {
    var chartTitle = "";
    var chartDatas = {
        dateArr: [],
        dataArr: []
    };
    for(var i=0; i<resp.length; i++) {
        var respData = resp[i];
        var respData_datas = respData.datas;
        var objTemp = {
            name: respData.title,
            type: 'line',
            data: [],
            markPoint: {
                data: [
                    { type: 'max', name: 'Max' },
                    { type: 'min', name: 'Min' }
                ]
            },
        };

        for(var j=0;j<respData_datas.length;j++) {

            if(!isSearch) { // 不是搜索，echart只显示15条
                if(j == 0){
                    chartTitle += respData_datas[j].NAME + " ";
                }
                //if(j > (respData_datas.length - 16) ){
                if(j < 15 ){
                    if(i == 0){
                        chartDatas.dateArr.unshift(respData_datas[j].DATADATE);
                    }
                    objTemp.data.unshift(respData_datas[j].DATA);
                }
            } else {
                if(j == 0){
                    chartTitle += respData_datas[j].NAME + " ";
                }
                if(i == 0){
                    chartDatas.dateArr.unshift(respData_datas[j].DATADATE);
                }
                objTemp.data.unshift(respData_datas[j].DATA);
            }
        }
        chartDatas.dataArr.push(objTemp);
    }
    drawZdChart(chartTitle, chartDatas);
}


//组装table datas 渲染table列表
// 组装table datas 渲染table列表
function handleZdTable(resp) {
    var hLen = resp.length;
    // 表格头部
    var zhouduHeaderHtml = "<tr><th width='300'>时间</th>";
    for(var i = 0; i < hLen; i++) {
        var respDatas = resp[i].datas;
        if(i == (hLen-1)) {
            zhouduHeaderHtml += "<th style='border-right: none;'>"+respDatas[0].NAME+"价格（"+respDatas[0].UNIT+"）</th>";
        } else {
            zhouduHeaderHtml += "<th>"+respDatas[0].NAME+"价格（"+respDatas[0].UNIT+"）</th>";
        }

    }
    zhouduHeaderHtml += "<th style='width:17px;'></th></tr>";
    $("#table-zhoudu-header").html(zhouduHeaderHtml);

    // 表格数据
    var zhouduHtml = "";
    var tableDatas = [];
    var respDatas0 = resp[0].datas;

    //var rdLen = respDatas0.length > 100 ? 100 : respDatas0.length;
    var rdLen = respDatas0.length;
    for(var j = 0; j < rdLen; j++) {
        if(hLen == 2) {
            if(j>=resp[0].datas.length || j>=resp[1].datas.length) {
                break;
            }
            var tableObj2 = {
                date: resp[0].datas[j].DATADATE,
                value1: resp[0].datas[j].DATA,
                value2: resp[1].datas[j].DATA
            };
            tableDatas.push(tableObj2);

        } else if(hLen == 3) {
            if(j>=resp[0].datas.length || j>=resp[1].datas.length || j>=resp[2].datas.length) {
                break;
            }
            var tableObj3 = {
                date: resp[0].datas[j].DATADATE,
                value1: resp[0].datas[j].DATA,
                value2: resp[1].datas[j].DATA,
                value3: resp[2].datas[j].DATA
            };
            tableDatas.push(tableObj3);
        } else {
            var tableObj1 = {
                date: resp[0].datas[j].DATADATE,
                value1: resp[0].datas[j].DATA
            };
            tableDatas.push(tableObj1);
        }
    }

    for(var k=0; k < tableDatas.length; k++) {
        if(hLen == 2) {
            zhouduHtml += "<tr><td width='300'>"+tableDatas[k].date+"</td>" +
                "<td>"+tableDatas[k].value1+"</td>" +
                "<td>"+tableDatas[k].value2+"</td></tr>";
        } else if(hLen == 3) {
            zhouduHtml += "<tr><td width='300'>"+tableDatas[k].date+"</td>" +
                "<td>"+tableDatas[k].value1+"</td>" +
                "<td>"+tableDatas[k].value2+"</td>" +
                "<td>"+tableDatas[k].value3+"</td></tr>";
        } else {
            zhouduHtml += "<tr><td width='300'>"+tableDatas[k].date+"</td>" +
                "<td>"+tableDatas[k].value1+"</td></tr>";
        }
    }
    $("#table-zhoudu").html(zhouduHtml);

}


// 获取周度数据


// 周度数据折线图

// 绘制echart图
function drawZdChart(chartTitle, chartDatas) {
    var unitName = '元/公斤';
    if(chartTitle.indexOf("豆油（零售）") > -1 || chartTitle.indexOf("花生油（零售）") > -1 || chartTitle.indexOf("菜籽油（零售）") > -1) {
        var tempArr = chartTitle.split(' ');
        if(tempArr && tempArr.length>2){
            var isTwoUnit = 0;
            for(var i=0; i<(tempArr.length-1); i++){
                if(tempArr[i].indexOf("豆油（零售）") > -1 || tempArr[i].indexOf("花生油（零售）") > -1 || tempArr[i].indexOf("菜籽油（零售）") > -1 ){
                    isTwoUnit += 1;
                } else {
                    isTwoUnit += 100;
                }
            }
            if(isTwoUnit > 100) {
                unitName = '元/公斤（元/升）';
            } else {
                unitName = '元/升';
            }
        } else {
            unitName = '元/升';
        }
    } else if(chartTitle.indexOf("牛奶(元/升)") > -1){
        var tempArr = chartTitle.split(' ');
        if(tempArr && tempArr.length>2){
            var isTwoUnit = 0;
            for(var i=0; i<(tempArr.length-1); i++){
                if(tempArr[i] == "牛奶(元/升)"){
                    isTwoUnit += 1;
                } else {
                    isTwoUnit += 100;
                }
            }
            if(isTwoUnit > 100) {
                unitName = '元/公斤（元/升）';
            } else {
                unitName = '元/升';
            }
        } else {
            unitName = '元/升';
        }
    }

    var subTitle = "批发价格走势";
    if(chartTitle.indexOf("零售") > -1 || chartTitle.indexOf("调和油") > -1 || chartTitle.indexOf("大米") > -1 || chartTitle.indexOf("食糖") > -1 || chartTitle.indexOf("食盐") > -1 ) {
        subTitle = "价格走势";
    }

    if(chartTitle.indexOf("牛奶(元/升)") > -1 || chartTitle.indexOf("酸奶") > -1 || chartTitle.indexOf("幼儿奶粉") > -1 || chartTitle.indexOf("中老年奶粉") > -1) {
        subTitle = "零售价格走势";
    }

    var optionZd = {
        color: ["#5470c6", "#95cd76","#c30d23"],
        title: {
            text: "全国 " + chartTitle + subTitle,
            left: 'center',
            top: 30
        },
        toolbox: {
            show: true,
            feature: {
                magicType: { type: ['line', 'bar'] },
            },
            right: 40,
            top: 40
        },
        grid: {
            top: '25%',
            left: '4%',
            right: '4%',
            bottom: '3%',
            containLabel: true
        },
        tooltip: {
            trigger: 'axis'
        },
        xAxis: {
            type: 'category',
            boundaryGap: false,
            data: chartDatas.dateArr,
            axisLabel: {
                interval: 0,
                rotate: 40
            }
        },
        yAxis: {
            name: unitName,
            type: 'value',
            axisLabel: {
                formatter: '{value} '
            }
        },
        series: chartDatas.dataArr
    };

    _chartPieZd = new drawCharts({ elem: 'mapBoxZd', option: optionZd, theme: null }).init();
}

// 周度数据搜索（按日期）
function searchZdData() {
    var indexIds = getCheckedCates();
    var zdStartDate = $("#zdStartDate").val() ? $("#zdStartDate").val() : this.getCurrentDateYmd();
    var zdEndDate = $("#zdEndDate").val()? $("#zdEndDate").val() : this.getCurrentDateYmd();
    loadList(indexIds, zdStartDate, zdEndDate, true);
}


// 获取选中的分类
function getCheckedCates() {
    var ids = "";
    $("input:checkbox[name='zdCateChks']:checked").each(function(i){
        if(0==i){
            ids = $(this).val();
        }else{
            ids += (","+$(this).val());
        }
    });
    return ids;
}


/**
 * ===========================周度监测数据相关 End=============================
 */


/**
 * ===========================其他数据相关 End=================================
 */

function load_qita_data(urlParam) {
    var type_index = "";
    if(urlParam.indexOf("_")!=-1){
        var type_arr = [];
        type_arr = urlParam.split("_");
        loadQtCategories2(type_arr[1]);
        if(type_arr[0] == 'jgncpgnqh'){
            $("#qitaSource").html("数据来源：郑州商品交易所、大连商品交易所");
        }else if(type_arr[0] == 'jgsczlgnqh') {
            $("#qitaSource").html("数据来源：上海期交易所、大连商品交易所、郑州商品交易所");
        }else if(type_arr[0] == 'jgncpgjxh' || type_arr[0] == 'jgncpgjqh' || type_arr[0] == 'jgsczlgjxh' || type_arr[0] == 'jgsczlgjqh'){
            $("#qitaSource").html("数据来源：商品价格网");
        }else if(type_arr[0] == 'scsjnfcp' || type_arr[0] == 'scsjsczl' || type_arr[0] == 'scsjgyxfp' ){
            $("#qitaSource").html("数据来源：国家统计局");
        }else if(type_arr[0] == 'jgsczlzdjc') {
            $("#qitaSource").html("数据来源：商务部市场运行监测系统");
        }else {
            $("#qitaSource").html("数据来源：商务部内贸统计监测平台");
        }
        $("#zdQtCatesFlg").val(type_arr[1]);
        changeClickStyle(type_arr[0]);
        showOrHideContainer(4);
        var loadObj = getLoadUrl(type_arr[0], type_arr[2]);
        loadQtData(loadObj);
    } else {
        type_index = "meitan";
        if(urlParam == 'jgncpgnqh'){
            $("#qitaSource").html("数据来源：郑州商品交易所、大连商品交易所");
        }else if(urlParam == 'jgsczlgnqh') {
            $("#qitaSource").html("数据来源：上海期交易所、大连商品交易所、郑州商品交易所");
        }else if(urlParam == 'jgncpgjxh' || urlParam == 'jgncpgjqh' || urlParam == 'jgsczlgjxh' || urlParam == 'jgsczlgjqh'){
            //$("#qitaSource").html("数据来源：商务部国际贸易经济合作研究院");
            $("#qitaSource").html("数据来源：商品价格网");
        }else if(urlParam == 'scsjnfcp' || urlParam == 'scsjsczl' || urlParam == 'scsjgyxfp' ){
            $("#qitaSource").html("数据来源：国家统计局");
        }else if(urlParam == 'jgsczlzdjc') {
            $("#qitaSource").html("数据来源：商务部市场运行监测系统");
        }else {
            $("#qitaSource").html("数据来源：商务部内贸统计监测平台");
        }

        $("#zdQtCatesFlg").val(type_index);
        changeClickStyle(urlParam);
        showOrHideContainer(4);
        var loadObj = getLoadUrl(urlParam, '');
        loadQtData(loadObj);
    }
}

function loadQtCategories(urlParam) {
    var qtCategories = qitaData.categoryDatas[urlParam];
    var qtCategoriesHtml = "";
    for(var i=0;i<qtCategories.length;i++) {
        qtCategoriesHtml += "<label><input type='radio' name='qtCatesRadio' title='"+qtCategories[i].name+"' data-url='"+urlParam+"' value='"+qtCategories[i].id+"' onchange='handleQtChange()'>"+qtCategories[i].name+"</label>";
    }
    $("#qtCategories").html(qtCategoriesHtml);
}

function loadQtCategories2(zFlg) {
    if(zFlg && zFlg == 'meitan') { // 还原父类选择为第一个
        $("#zdQtCates").children(":first").addClass("on");
        $("#zdQtCates").children(":first").siblings().removeClass("on");
    }
    var zdCategories2 = zhouduData.categoryDatas2[zFlg];
    var zdCategories2Html = "";
    for(var i=0;i<zdCategories2.length;i++) {
        zdCategories2Html += "<label><input type='radio' name='qtCatesRadio' " +
            " title='"+zdCategories2[i].name+"' data-url='jgsczlzdjc' value='"+zdCategories2[i].id+"' " +
            " onchange='handleQtChange()'>"+zdCategories2[i].name+"</label>";
    }
    $("#qtCategories").html(zdCategories2Html);

    if(zFlg == 'meitan') {
        $("#zdQtCates").children(":first").addClass("on");
        $("#zdQtCates").children(":first").siblings().removeClass("on");
    } else if(zFlg == 'chengpinyou') {
        $("#zdQtCates").children().eq(1).addClass("on");
        $("#zdQtCates").children().eq(1).siblings().removeClass("on");
    } else if(zFlg == 'gangcai') {
        $("#zdQtCates").children().eq(2).addClass("on");
        $("#zdQtCates").children().eq(2).siblings().removeClass("on");
    } else if(zFlg == 'xiangjiao') {
        $("#zdQtCates").children().eq(3).addClass("on");
        $("#zdQtCates").children().eq(3).siblings().removeClass("on");
    }  else if(zFlg == 'huafei') {
        $("#zdQtCates").children().eq(4).addClass("on");
        $("#zdQtCates").children().eq(4).siblings().removeClass("on");
    } else if(zFlg == 'yousejinshu') {
        $("#zdQtCates").children().eq(5).addClass("on");
        $("#zdQtCates").children().eq(5).siblings().removeClass("on");
    } else if(zFlg == 'shuini') {
        $("#zdQtCates").children().eq(6).addClass("on");
        $("#zdQtCates").children().eq(6).siblings().removeClass("on");
    } else if(zFlg == 'jichuhuaxue') {
        $("#zdQtCates").children().eq(7).addClass("on");
        $("#zdQtCates").children().eq(7).siblings().removeClass("on");
    }  else if(zFlg == 'boli') {
        $("#zdQtCates").children().eq(8).addClass("on");
        $("#zdQtCates").children().eq(8).siblings().removeClass("on");
    } else {
        $("#zdQtCates").children().eq(0).addClass("on");
        $("#zdQtCates").children().eq(0).siblings().removeClass("on");
    }

    $("input[type=radio][name=qtCatesRadio][value='"+zdCategories2[0].id+"']").attr("checked",true);

    if(zFlg != $("#zdQtCatesFlg").val()) {
        var rObj = {
            url: "/cif/getWeekLineChart2019.fhtml",
            data: {
                indexId: zdCategories2[0].id,
                startDate: '',
                endDate: '',
                flg: 2
            }
        };
        loadQtData(rObj);
    }
    $("#zdQtCatesFlg").val(zFlg);
}

function loadQtData(loadObj) {
    $.ajax({
        type : "POST",
        url : loadObj.url,
        data : loadObj.data,
        success : function(json) {
            console.log("loadQtData", json)
            var datas = json.datas;
            var table = json.table;

            if(loadObj.data.flg == 3) table = datas;
            var qtIndexId;
            var qtMinDate;
            if(loadObj.data.flg == 2) {
                qtIndexId = loadObj.data.indexId;
                qtMinDate = datas[0].DATADATE;
            } else if(loadObj.data.flg == 3) {
                qtIndexId = loadObj.data.cateId;
                qtMinDate = "";
            } else {
                qtIndexId = loadObj.data.commId;
                qtMinDate = datas[0].RPTDATE;
            }
            $("#qtIndexId").val(qtIndexId);
            $("#qtMinDate").val(qtMinDate);
            $("#qtStartDate").val(json.startDate);
            $("#qtEndDate").val(json.endDate);
            $("#qtTitle").val(json.title);
            $("#qtUnit").val(json.unit);

            var qtDateArr = new Array();
            var qtDataArr = new Array();
            var qtDataArr2 = new Array();
            for (var i = 0; i < datas.length; i++) {
                if(loadObj.data.flg == 2) {
                    qtDateArr[i] = datas[i].DATADATE;
                    qtDataArr[i] = datas[i].DATA;
                } else if(loadObj.data.flg == 3) {
                    qtDateArr[i] = datas[i].date;
                    qtDataArr[i] = datas[i].trend;
                    qtDataArr2[i] = datas[i].value;
                } else {
                    qtDateArr[i] = datas[i].RPTDATE;
                    qtDataArr[i] = datas[i].PRICE;
                }

            }
            $("#qtDateArr").val(qtDateArr);
            $("#qtDataArr").val(qtDataArr);

            console.log("oadObj.data.flg====", loadObj.data.flg);
            console.log(qtDateArr, qtDataArr, qtDataArr2, json.unit);

            // 绘制echart图
            if(loadObj.data.flg == 3) {
                drawChartQtInfo2(json.title, qtDateArr, qtDataArr, qtDataArr2, json.unit);
            } else {
                drawChartQtInfo(json.title, qtDateArr, qtDataArr, false, json.unit);
            }

            // 组装Table List
            var titleTemp2;
            var titleTemp3;
            var titleTemp4;
            if(loadObj.data.flg == 3) {
                titleTemp2 = "产量";
                if(loadObj.data.cateId != '31' && loadObj.data.cateId != '41'&& loadObj.data.cateId != '42'
                    && loadObj.data.cateId != '32'&& loadObj.data.cateId != '33' && loadObj.data.cateId != '34'
                    && loadObj.data.cateId != '35'&& loadObj.data.cateId != '36' && loadObj.data.cateId != '37'
                    && loadObj.data.cateId != '38'&& loadObj.data.cateId != '39' && loadObj.data.cateId != '40'
                    && loadObj.data.cateId != '51'&& loadObj.data.cateId != '52' && loadObj.data.cateId != '53'
                    && loadObj.data.cateId != '54'&& loadObj.data.cateId != '55' && loadObj.data.cateId != '56'
                    && loadObj.data.cateId != '57'&& loadObj.data.cateId != '58'&& loadObj.data.cateId != '59'&& loadObj.data.cateId != '60'){
                    titleTemp3 = "同比变化";
                }
                titleTemp4 = "同比（%）";
            } else {
                titleTemp2 = "价格";
                titleTemp3 = "环比变化";
                titleTemp4 = "环比（%）";
            }

            var table_header_temp = "";
            if(loadObj.data.cateId != '31' && loadObj.data.cateId != '41'&& loadObj.data.cateId != '42'
                && loadObj.data.cateId != '32'&& loadObj.data.cateId != '33' && loadObj.data.cateId != '34'
                && loadObj.data.cateId != '35'&& loadObj.data.cateId != '36' && loadObj.data.cateId != '37'
                && loadObj.data.cateId != '38'&& loadObj.data.cateId != '39' && loadObj.data.cateId != '40'
                && loadObj.data.cateId != '51'&& loadObj.data.cateId != '52' && loadObj.data.cateId != '53'
                && loadObj.data.cateId != '54'&& loadObj.data.cateId != '55' && loadObj.data.cateId != '56'
                && loadObj.data.cateId != '57'&& loadObj.data.cateId != '58'&& loadObj.data.cateId != '59'&& loadObj.data.cateId != '60'){
                table_header_temp =  "<tr>" +
                    "<th width='200'>时间</th>" +
                    "<th width='200'>"+titleTemp2+"（"+json.unit+"）</th>" +
                    "<th width='200'>"+titleTemp3+"（"+json.unit+"）</th>" +
                    "<th>"+titleTemp4+"</th>" +
                    "</tr>";
            } else {
                table_header_temp =  "<tr>" +
                    "<th width='200'>时间</th>" +
                    "<th width='200'>"+titleTemp2+"（"+json.unit+"）</th>" +
                    "<th>"+titleTemp4+"</th>" +
                    "</tr>";
            }

            var table_header = table_header_temp;

            $("#tableQtHeader").html(table_header);
            var table_html = "";
            for(var i=table.length-1; i>=0; i--){
                var priceTemp = "";
                if(loadObj.data.flg == 2 || loadObj.data.flg == 3) {
                    priceTemp = table[i].value;
                } else {
                    priceTemp = table[i].price;
                }

                var table_html_temp = "";

                if(loadObj.data.cateId != '31' && loadObj.data.cateId != '41'&& loadObj.data.cateId != '42'
                    && loadObj.data.cateId != '32'&& loadObj.data.cateId != '33' && loadObj.data.cateId != '34'
                    && loadObj.data.cateId != '35'&& loadObj.data.cateId != '36' && loadObj.data.cateId != '37'
                    && loadObj.data.cateId != '38'&& loadObj.data.cateId != '39' && loadObj.data.cateId != '40'
                    && loadObj.data.cateId != '51'&& loadObj.data.cateId != '52' && loadObj.data.cateId != '53'
                    && loadObj.data.cateId != '54'&& loadObj.data.cateId != '55' && loadObj.data.cateId != '56'
                    && loadObj.data.cateId != '57'&& loadObj.data.cateId != '58'&& loadObj.data.cateId != '59'&& loadObj.data.cateId != '60'){

                    var difference = 0;
                    var trend = 0;
                    if(priceTemp == 0 || priceTemp == '0'){
                        priceTemp = "-";
                        difference = "-";
                        trend = "-";
                    } else {
                        difference = table[i].difference;
                        trend = table[i].trend;
                    }

                    table_html_temp = "<tr>" +
                        "<td  width='200'>"+table[i].date+"</td>" +
                        "<td width='200'>"+priceTemp+"</td>" +
                        "<td width='200'>"+difference+"</td>" +
                        "<td>"+trend+"</td>" +
                        "</tr>";
                } else {
                    table_html_temp =  "<tr>" +
                        "<td  width='200'>"+table[i].date+"</td>" +
                        "<td width='200'>"+priceTemp+"</td>" +
                        "<td>"+table[i].trend+"</td>" +
                        "</tr>";
                }

                table_html += table_html_temp;
            }
            $("#tableQtList").html(table_html);
        }
    });
}

function getLoadUrl(urlParam, cId) {
    $("#qt-data-search").show();
    var returnObj = {
        url: '',
        data: {}
    };
    var radioVal = "";
    if(urlParam == 'jgncpgnqh'){  // 农副产品-国内期货价格
        returnObj.url =  "/cif/getWeekLineChartWithMMS2019.fhtml";
        returnObj.data = {
            commId: cId ? cId: '2101',
            startDate: '',
            endDate: '',
            flg: 1
        };
        radioVal = returnObj.data.commId;
    } else if(urlParam == 'jgncpgjxh') {  // 农副产品-国际现货价格
        returnObj.url =  "/cif/getWeekLineChart2019.fhtml";
        returnObj.data = {
            indexId: cId ? cId: '224096',
            startDate: '',
            endDate: '',
            flg: 2
        };
        radioVal = returnObj.data.indexId;
    } else if(urlParam == 'jgncpgjqh') { // 农副产品-国际期货价格
        returnObj.url =  "/cif/getWeekLineChart2019.fhtml";
        returnObj.data = {
            indexId: cId ? cId: '224120',
            startDate: '',
            endDate: '',
            flg: 2
        };
        radioVal = returnObj.data.indexId;
    } else if(urlParam == 'jgsczlzdjc') { // 生产资料-周度监测数据
        returnObj.url =  "/cif/getWeekLineChart2019.fhtml";
        returnObj.data = {
            indexId: cId ? cId: '223962',
            startDate: '',
            endDate: '',
            flg: 2
        };
        radioVal = returnObj.data.indexId;
    }  else if(urlParam == 'jgsczlgnqh') { // 生产资料-国内期货价格
        returnObj.url =  "/cif/getWeekLineChartWithMMP2019.fhtml";
        returnObj.data = {
            commId: cId ? cId: '1100',
            startDate: '',
            endDate: '',
            flg: 1
        };
        radioVal = returnObj.data.commId;
    } else if(urlParam == 'jgsczlgjxh') { // 生产资料-国际现货价格
        returnObj.url =  "/cif/getWeekLineChart2019.fhtml";
        returnObj.data = {
            indexId: cId ? cId: '224721',
            startDate: '',
            endDate: '',
            flg: 2
        };
        radioVal = returnObj.data.indexId;
    } else if(urlParam == 'jgsczlgjqh') { // 生产资料-国际期货价格
        returnObj.url =  "/cif/getWeekLineChart2019.fhtml";
        returnObj.data = {
            indexId: cId ? cId: '224739',
            startDate: '',
            endDate: '',
            flg: 2
        };
        radioVal = returnObj.data.indexId;
    } else if(urlParam == 'scsjnfcp' || urlParam == 'scsjsczl' || urlParam == 'scsjgyxfp') { // 生产-农副产品 || 生产-生产资料 || 生产-工业消费品
        var cateId  = urlParam == 'scsjnfcp' ? '2' : urlParam == 'scsjsczl' ? '31' : '51';
        returnObj.url =  "/cif/getBoardChartList2019.fhtml";
        returnObj.data = {
            cateId: cId ? cId: cateId,
            flg: 3
        };
        radioVal = returnObj.data.cateId;
        $("#qt-data-search").hide();
    }

    if(urlParam == 'jgsczlzdjc') {
        $("#zdQtCates").show();
        var zdQtCatesFlg = $("#zdQtCatesFlg").val();
        if(zdQtCatesFlg){
            loadQtCategories2(zdQtCatesFlg); // 加载分类(周度监测数据)
        } else {
            loadQtCategories2("meitan"); // 加载分类(周度监测数据)
        }
    } else {
        $("#zdQtCates").hide();
        loadQtCategories(urlParam); // 加载分类
    }
    $("input[name=qtCatesRadio][value="+radioVal+"]").attr("checked",true);
    return returnObj;
}

// 绘制其他-echart图
function drawChartQtInfo(title, dateArr, dataArr, isSearch, unit) {
    if(!isSearch) {
        if(dateArr && dateArr.length > 15){
            dateArr = dateArr.slice(dateArr.length - 15);
            dataArr = dataArr.slice(dataArr.length - 15);
        }
    }
    var optionQtInfo = {
        color: ["#5470c6"],
        grid: {
            top: '25%',
            left: '4%',
            right: '4%',
            bottom: '3%',
            containLabel: true
        },
        tooltip: {
            trigger: 'axis'
        },
        title: {
            text: title,
            left: 'center',
            top: 30
        },
        toolbox: {
            show: true,
            feature: {
                magicType: { type: ['line', 'bar'] },
            },
            right: 40,
            top: 40
        },

        xAxis: {
            type: 'category',
            boundaryGap: false,
            data: dateArr,
            axisLabel: {
                interval: 0,
                rotate: 40
            }
        },
        yAxis: {
            name: unit ? unit : "元/吨",
            type: 'value',
            axisLabel: {
                formatter: '{value} '
            }
        },
        series: [
            {
                // name: 'Highest',
                type: 'line',
                data: dataArr,
                markPoint: {
                    data: [
                        { type: 'max', name: 'Max' },
                        { type: 'min', name: 'Min' }
                    ]
                },
                stack: 'a',
                areaStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        {
                            offset: 0,
                            color: 'rgba(84,112,198,0.8)'
                        },
                        {
                            offset: 1,
                            color: 'rgba(84,112,198,0.3)'
                        }
                    ])
                },
            }
        ]
    };

    _chartPieQtInfo = new drawCharts({ elem: 'mapBoxQt', option: optionQtInfo, theme: null }).init();
}


function drawChartQtInfo2(title, dateArr, dataArr, dataArr2, unit) {
    var optionQtInfo2 = {
        title : {
            left: 'center',
            text : title,
            top : 5
        },
        tooltip : {
            trigger: 'axis',
            axisPointer : {            // 坐标轴指示器，坐标轴触发有效
                type : 'shadow'        // 默认为直线，可选为：'line' | 'shadow'
            }
        },
        legend: {
            data:['涨跌幅','产量'],
            top:35
        },
        grid: {
            left: '3%',
            right: '4%',
            bottom: '15%',
            containLabel: true
        },
        xAxis : [
            {
                axisLabel: {
                    //interval:0,
                    rotate:60
                },
                type : 'category',
                data : dateArr
            }
        ],
        yAxis : [
            {
                type : 'value',
                name : '产量'+'('+unit+')',
                splitLine:{
                    show:false
                }
            },
            {
                type: 'value',
                name: '涨跌幅(%)',
                splitLine:{
                    show:false
                }
            }
        ],
        dataZoom: [{
            type: 'inside',
            start: 30,
            end: 100,
            bottom:0
        }, {
            start: 0,
            end: 100,
            bottom:10,
            handleIcon: 'M10.7,11.9v-1.3H9.3v1.3c-4.9,0.3-8.8,4.4-8.8,9.4c0,5,3.9,9.1,8.8,9.4v1.3h1.3v-1.3c4.9-0.3,8.8-4.4,8.8-9.4C19.5,16.3,15.6,12.2,10.7,11.9z M13.3,24.4H6.7V23h6.6V24.4z M13.3,19.6H6.7v-1.4h6.6V19.6z',
            handleSize: '80%',
            handleStyle: {
                color: '#fff',
                shadowBlur: 3,
                shadowColor: 'rgba(0, 0, 0, 0.6)',
                shadowOffsetX: 2,
                shadowOffsetY: 2
            }
        }],
        series : [
            {
                name:'产量',
                type:'bar',
                barWidth : 20,
                color:'#ff7575',
                stack: 'aa',
                data: dataArr2
            },
            {
                name:'涨跌幅',
                type:'line',
                yAxisIndex: 1,
                color:'#be77ff',
                data: dataArr
            }
        ]
    };

    _chartPieQtInfo2 = new drawCharts({ elem: 'mapBoxQt', option: optionQtInfo2, theme: null }).init();
}

function handleQtChange(url,val) {
    var rUrl = url ? url : $("input[name=qtCatesRadio]:checked").attr("data-url");
    var rVal = val ? val : $("input[name=qtCatesRadio]:checked").val();
    var rObj = getLoadUrl(rUrl, rVal);
    loadQtData(rObj);
}

function searchQtData() {
    var qtStartDate = $("#qtStartDate").val() ? $("#qtStartDate").val() : this.getCurrentDateYmd();
    var qtEndDate = $("#qtEndDate").val() ? $("#qtEndDate").val() : this.getCurrentDateYmd();
    var qtTitle = $("#qtTitle").val();
    var qtUnit = $("#qtUnit").val();
    var qtDateArr = $("#qtDateArr").val().split(",");
    var qtDataArr = $("#qtDataArr").val().split(",");
    var newQtDateArr;
    var newQtDataArr;
    var startIndex = 0;
    var endIndex = 0;
    $.each(qtDateArr,function(idx){
        if((new Date(qtDateArr[idx]) > new Date(qtStartDate)) && startIndex == 0){
            startIndex = idx;
        }
        if(new Date(qtDateArr[idx]) < new Date(qtEndDate)){
            endIndex = idx;
        }
    });
    newQtDateArr = qtDateArr.slice(startIndex, endIndex+1);
    newQtDataArr = qtDataArr.slice(startIndex, endIndex+1);

    drawChartQtInfo(qtTitle,newQtDateArr,newQtDataArr , true, qtUnit);
}

/**
 * ===========================其他数据相关 End================================
 */

/**
 * ===========================新闻 Start======================================
 */
function load_news(urlParam) {
    changeClickStyle(urlParam);
    showOrHideContainer(5,6);
    var baseData = getBaseData(urlParam, '');
    loadNewsData(baseData);
}

function getBaseData(urlParam, nodeId) {
    var returnObj = {
        url: '',
        data: {}
    };
    var newsListMoreHtml = "";

    if(urlParam == 'qcxfsj' || urlParam == 'qcxfqk' || urlParam == 'shxfplsze' || urlParam == 'czsr'){
        var nodeIdTemp;
        if(urlParam == 'qcxfsj') {
            nodeIdTemp = "35869";
        } else if(urlParam == 'qcxfqk') {
            nodeIdTemp = "35278";
        } else if(urlParam == 'shxfplsze') {
            nodeIdTemp = "35276";
        } else if(urlParam == 'czsr') {
            nodeIdTemp = "35332";
        } else {
            nodeIdTemp = "35869";
        }
        returnObj.url =  "/cif/getMaxYearByNodeIdFor2019.fhtml";
        returnObj.data = {
            nodeId: nodeId ? nodeId: nodeIdTemp,
        };
        newsListMoreHtml = " <h2>往期数据</h2><a href='javascript:void(0);' class='more' onclick='load_news_list(1,"+returnObj.data.nodeId+")'>更多&gt;&gt;</a>";
    } else if(urlParam == 'fdqshxfplsze' || urlParam == 'gnsczz' || urlParam == 'jmsrhxfzc'
        || urlParam == 'qgdzswjyejzs' || urlParam == 'qgwslsejzs' || urlParam == 'gnlysjqk' || urlParam == 'shydl'
        || urlParam == 'gysczzsd' || urlParam == 'gdzctz' || urlParam == 'hbgyl') {
        var nodeIdTemp;
        if(urlParam == 'fdqshxfplsze') {
            nodeIdTemp = "35277";
        } else if(urlParam == 'gnsczz') {
            nodeIdTemp = "35327";
        } else if(urlParam == 'jmsrhxfzc') {
            nodeIdTemp = "35909";
        } else if(urlParam == 'qgdzswjyejzs') {
            nodeIdTemp = "35930";
        } else if(urlParam == 'qgwslsejzs') {
            nodeIdTemp = "35929";
        } else if(urlParam == 'gnlysjqk') {
            nodeIdTemp = "35931";
        } else if(urlParam == 'shydl') {
            nodeIdTemp = "35932";
        } else if(urlParam == 'gysczzsd') {
            nodeIdTemp = "35933";
        } else if(urlParam == 'gdzctz') {
            nodeIdTemp = "35934";
        } else if(urlParam == 'hbgyl') {
            nodeIdTemp = "35949";
        } else {
            nodeIdTemp = "35277";
        }
        returnObj.url =  "/cif/getMaxYearByNodeIdFor2019.fhtml";
        returnObj.data = {
            nodeId: nodeId ? nodeId: nodeIdTemp,
        };
        newsListMoreHtml = " <h2>往期数据</h2><a href='javascript:void(0);' class='more' onclick='load_news_list(2,"+returnObj.data.nodeId+")'>更多&gt;&gt;</a>";
    } else if(urlParam == 'hysj' || urlParam == 'lssj') {
        var nodeIdTemp;
        if(urlParam == 'hysj') {
            nodeIdTemp = "35377";
        } else if(urlParam == 'lssj') {
            nodeIdTemp = "35326";
        } else {
            nodeIdTemp = "35377";
        }
        returnObj.url =  "/cif/getContentFor2019DataCenter.fhtml";
        returnObj.data = {
            nodeId: nodeId ? nodeId: nodeIdTemp,
        };
        newsListMoreHtml = " <h2>往期数据</h2><a href='javascript:void(0);' class='more' onclick='load_news_list(3,"+returnObj.data.nodeId+")'>更多&gt;&gt;</a>";
    }


    $("#news-list-more").html(newsListMoreHtml);
    return returnObj;
}

function loadNewsData(baseData){
    $.ajax({
        type : "POST",
        url: baseData.url,
        data: baseData.data,
        success: function(resp) {
            var newsContentHtml = "";
            newsContentHtml = "<h1>"+resp.title+"</h1>" +
                "<div class='info'>" +
                "<span class='date'>"+resp.publishDate+"</span>" +
                "<span>文章来源：</span><span class='source'>"+resp.source+"</span></div>" +
                "<div class='article'>"+resp.content+"</div>";
            $("#news-content").html(newsContentHtml);

            var newsListHtml = "";
            var newsList  = resp.list;
            if(newsList && newsList.length>0){
                var newsListTemp = [];
                if(newsList.length>6){
                    newsListTemp = newsList.slice(0,6);
                } else {
                    newsListTemp = newsList;
                }
                for(var i=0; i<newsListTemp.length; i++){
                    var newsObj = newsListTemp[i];
                    newsListHtml += "<li><a href='/cif/html"+newsObj.path+"' target='_blank'>"+newsObj.title+"</a><span class='date'>"+newsObj.publishDate+"</span></li>";
                }
            } else {
                newsListHtml = "<span style='color:#656565;'></span>";
                $("#news-list-more").html("<h2>往期数据</h2>");
            }
            $("#news-list").html(newsListHtml);
        }
    });
}
/**
 * ===========================新闻 End========================================
 */

/**
 * ===========================新闻列表 Start==================================
 */
function load_news_list(flag, nodeId) {
    showOrHideContainer(7);
    var postUrl = "";
    if(flag == 1){
        postUrl = "/cif/getMaxYearByNodeIdFor2019.fhtml";
    } else if(flag == 2) {
        postUrl = "/cif/getMaxYearByNodeIdFor2019.fhtml";
    } else {
        postUrl = "/cif/getContentFor2019DataCenter.fhtml";
    }
    $("#moreUrl").val(postUrl);
    $("#moreNodeId").val(nodeId);
    loadMoreData(postUrl, nodeId, function(data) {
        handleNewsList(data, 0);
    });
}

function loadMoreData(postUrl, nodeId, callback) {
    $.ajax({
        type : "POST",
        url: postUrl,
        data: {
            nodeId: nodeId
        },
        success: function(resp) {
            callback(resp.list);
        }
    });
}

function handleNewsList(newsList, pageNo) {
    var maxN = 0;
    if((newsList.length/6) > 3){
        maxN = (newsList.length/6) - 3;
        if(parseInt(pageNo) > maxN) {
            alert("无法加载更多数据！");
            return;
        }
    }else {
        if(parseInt(pageNo) != 0){
            alert("无法加载更多数据！");
            return;
        }
    }

    var newsListArr = [];
    if(newsList && newsList.length>0){
        var len = newsList.length+1;
        var arrTemp = [];
        for(var i=1;i<len;i++){
            if(i%6 != 0){
                arrTemp.push(newsList[i-1]);
                if(i == (len-1)) {
                    newsListArr.push(arrTemp);
                }
            } else {
                arrTemp.push(newsList[i-1]);
                newsListArr.push(arrTemp);
                arrTemp = [];
            }
        }
    }
    if(newsListArr.length>3) {
        newsListArr = newsListArr.slice(0, parseInt(pageNo)+3);
    }

    var moreHtml = "";
    for(var j =0;j<newsListArr.length;j++) {
        var singleArr = newsListArr[j];
        var singleHtml = "<div class='news-items news-items1'><ul>";
        for(var k=0;k<singleArr.length;k++){
            var nObj = singleArr[k];
            var npath = nObj.PATH ? nObj.PATH : nObj.path;
            var ntitle = nObj.TITLE ? nObj.TITLE : nObj.title;
            singleHtml += "<li><a href='/cif/html"+npath+"' target='_blank'>"+ntitle+"</a><span class='date'>"+nObj.publishDate+"</span></li>";
        }
        singleHtml += "</ul></div>";
        moreHtml += singleHtml;
    }
    $("#moreListPageNo").val(parseInt(pageNo)+1);
    $("#moreList").html(moreHtml);
}

function clickMore(){
    var pageNo = $("#moreListPageNo").val();
    loadMoreData($("#moreUrl").val(), $("#moreNodeId").val(), function(data) {
        handleNewsList(data, pageNo);
    });
}
/**
 * ===========================新闻列表 End====================================
 */


/**
 * ===========================other tools Start==============================
 */
// 获取当前日期 yyyy-MM-dd
function getCurrentDateYmd() {
    var nowDate = new Date();
    var year = nowDate.getFullYear();
    var mon = nowDate.getMonth() + 1;
    var date = nowDate.getDate();
    return year + '-' + mon + '-' + date;
}

// 获取前一天
function yesterdayYmd() {
    var time=(new Date).getTime()-48*60*60*1000;
    var now = new Date(time);
    //var now = new Date('2025-02-27');
    var yesterday=now.getFullYear() + "-" + (now.getMonth()> 8 ? (now.getMonth() + 1) : "0" + (now.getMonth() + 1)) + "-" +(now.getDate()> 9 ? (now.getDate()) : "0" + (now.getDate()));
    return yesterday;
}

// 获取周度数据选中类别name
function getCheckedNames(){
    var returnNames = [];
    $("input:checkbox[name='zdCateChks']:checked").each(function(i){
        returnNames.push($(this).attr("title"));
    });
    return returnNames;
};

// container显隐控制
function showOrHideContainer(num1, num2) {
    for(var i=1;i<9;i++){
        if(i == num1 || i == num2){
            $("#container"+i).show();
        } else {
            $("#container"+i).hide();
        }
    }
}

/**
 * ===========================other tools End================================
 */


/**
 * =========================== 非结构化数据 Start================================
 */

function load_new_data(urlParam) {
    $("#current_sel").val(urlParam);
    changeClickStyle(urlParam);
    showOrHideContainer(8);
    show_select_type_box(urlParam);
    loadNewData();
}

function loadNewData(selType) {
    var current_sel = $("#current_sel").val()
    var url = "";
    var data = {};
    if(current_sel && current_sel == 'qgdzswjyejzs'){
        url="/cif/getDataCenterQgdzswjye.fhtml";
        var newSourceHtml = "数据来源：国家统计局";
        $("#newSource").html(newSourceHtml);
    } else if(current_sel == 'gdzctz'){
        url="/cif/getDataCenterGdzctz.fhtml";
        var newSourceHtml = "数据来源：国家统计局";
        $("#newSource").html(newSourceHtml);
    } else if(current_sel == 'qgwslsejzs'){
        url="/cif/getDataCenterQgwslse.fhtml";
        var newSourceHtml = "数据来源：国家统计局";
        $("#newSource").html(newSourceHtml);
    } else if(current_sel == 'gysczzsd'){
        url="/cif/getDataCenterGysczzsd.fhtml";
        var newSourceHtml = "数据来源：国家统计局";
        $("#newSource").html(newSourceHtml);
    } else if(current_sel == 'hbgyl'){
        url="/cif/getDataCenterHbgyl.fhtml";
        var newSourceHtml = "数据来源：中国人民银行";
        $("#newSource").html(newSourceHtml);
    } else if(current_sel == 'gnsczz'){
        url="/cif/getDataCenterGnsczz.fhtml";
        var dataType = 'GDP';
        if (selType && selType == 1) {
            dataType = 'GDP';
        } else if (selType == 2) {
            dataType = '第一产业';
        } else if (selType == 3) {
            dataType = '第二产业';
        } else if (selType == 4) {
            dataType = '第三产业';
        } else if (selType == 5) {
            dataType = '农林牧渔业';
        } else if (selType == 6) {
            dataType = '工业';
        } else if (selType == 7) {
            dataType = '制造业';
        } else if (selType == 8) {
            dataType = '建筑业';
        } else if (selType == 9) {
            dataType = '批发和零售业';
        } else if (selType == 10) {
            dataType = '交通运输、仓储和邮政业';
        } else if (selType == 11) {
            dataType = '住宿和餐饮业';
        } else if (selType == 12) {
            dataType = '金融业';
        } else if (selType == 13) {
            dataType = '房地产业';
        } else if (selType == 14) {
            dataType = '信息传输、软件和信息技术服务业';
        } else if (selType == 15) {
            dataType = '租赁和商务服务业';
        } else if (selType == 16) {
            dataType = '其他行业';
        }
        data = {
            dataType: dataType
        }

        var newSourceHtml = "<p>注：	</p>" +
            "<p>1.总量按现价计算，增速按不变价计算；</p>" +
            "<p>2.三次产业分类依据国家统计局2018年修订的《三次产业划分规定》；</p>" +
            "<p>3.行业分类采用《国民经济行业分类（GB/T 4754－2017）》；</p>" +
            "<p>4.本表GDP总量数据中，有的不等于各产业（行业）之和，是由于数值修约误差所致，未作机械调整。</p>" +
            "<p>数据来源：国家统计局</p>";
        $("#newSource").html(newSourceHtml);
    } else if(current_sel == 'shxfplsze'){
        url="/cif/getDataCenterShxfplsze.fhtml";
        var dataType = '社会消费品零售总额';
        if (selType && selType == 1) {
            dataType = '社会消费品零售总额';
        } else if (selType == 2) {
            dataType = '按经营地分(城镇)';
        } else if (selType == 3) {
            dataType = '按经营地分(乡村)';
        } else if (selType == 4) {
            dataType = '按消费类型分(餐饮收入)';
        } else if (selType == 5) {
            dataType = '按消费类型分(商品零售)';
        } else {
            dataType = '社会消费品零售总额';
        }
        data = {
            dataType: dataType
        };
        var newSourceHtml = "<p>注：	</p>" +
            "<p>1.此表速度均为未扣除价格因素的名义增速；</p>" +
            "<p>2.此表中部分数据因四舍五入，存在总计与分项合计不等的情况；</p>" +
            "<p>3.行业分类采用《国民经济行业分类（GB/T 4754－2017）》；</p>" +
            "<p>数据来源：国家统计局</p>";
        $("#newSource").html(newSourceHtml);
    } else if(current_sel == 'shxfplsze2'){
        url="/cif/getDataCenterShxfplsze2.fhtml";
        var dataType = '限额以上单位商品零售';
        if (selType && selType == 1) {
            dataType = '限额以上单位商品零售';
        } else if (selType == 2) {
            dataType = '粮油、食品类';
        } else if (selType == 3) {
            dataType = '饮料类';
        } else if (selType == 4) {
            dataType = '烟酒类';
        } else if (selType == 5) {
            dataType = '服装、鞋帽、针纺织品类';
        } else if (selType == 6) {
            dataType = '化妆品类';
        } else if (selType == 7) {
            dataType = '金银珠宝类';
        } else if (selType == 8) {
            dataType = '日用品类';
        } else if (selType == 9) {
            dataType = '家用电器和音像器材类';
        } else if (selType == 10) {
            dataType = '中西药品类';
        } else if (selType == 11) {
            dataType = '文化办公用品类';
        } else if (selType == 12) {
            dataType = '家具类';
        } else if (selType == 13) {
            dataType = '通讯器材类';
        } else if (selType == 14) {
            dataType = '石油及制品类';
        } else if (selType == 15) {
            dataType = '汽车类';
        } else if (selType == 16) {
            dataType = '建筑及装潢材料类';
        }
        data = {
            dataType: dataType
        };
        var newSourceHtml = "<p>注：	</p>" +
            "<p>1.此表速度均为未扣除价格因素的名义增速。</p>" +
            "<p>2.此表中部分数据因四舍五入，存在总计与分项合计不等的情况。</p>" +
            "<p>数据来源：国家统计局</p>";
        $("#newSource").html(newSourceHtml);
    } else if(current_sel == 'spls'){
        url="/cif/getDataCenterSpls.fhtml";
        var newSourceHtml = "数据来源：国家统计局";
        $("#newSource").html(newSourceHtml);
    } else if(current_sel == 'xscysr'){
        url="/cif/getDataCenterXscysr.fhtml";
        var newSourceHtml = "数据来源：国家统计局";
        $("#newSource").html(newSourceHtml);
    } else if(current_sel == 'gnly'){
        url="/cif/getDataCenterGnly.fhtml";
        var newSourceHtml = "数据来源：国家统计局";
        $("#newSource").html(newSourceHtml);
    } else {
        url="/cif/getDataCenterCzsz.fhtml";
        var newSourceHtml = "数据来源：财政部";
        $("#newSource").html(newSourceHtml);
    }
    $.ajax({
        type : "POST",
        url : url,
        data : data,
        success : function(json) {
            if(current_sel && current_sel == 'qgdzswjyejzs'){
                handleQgdzswjye(json, selType);
            } else if(current_sel == 'gdzctz'){
                handleGdzctz(json, selType);
            } else if(current_sel == 'qgwslsejzs'){
                handleQgwslse(json, selType);
            } else if(current_sel == 'gysczzsd'){
                handleQysczzsd(json, selType);
            } else if(current_sel == 'hbgyl'){
                handleHbgyl(json, selType);
            } else if(current_sel == 'gnsczz'){
                handleGnsczz(json, selType);
            } else if(current_sel == 'shxfplsze'){
                handleShxfplsze(json, selType);
            } else if(current_sel == 'shxfplsze2'){
                handleShxfplsze2(json, selType);
            } else if(current_sel == 'spls'){
                handleSpls(json, selType);
            } else if(current_sel == 'xscysr'){
                handleXscysr(json, selType);
            } else if(current_sel == 'gnly'){
                handleGnly(json, selType);
            } else {
                handleCzsz(json, selType);
            }
        }
    });
}

function handleCzsz(json, selType){
    var dataList = json.datas;
    var monthList = [];
    var moneyList = [];
    var speedList = [];
    var title = "累计收入";
    var table_title = "累计收入";
    for(var i = 0; i < dataList.length; i++){
        if(selType && selType == '2'){
            monthList.push(dataList[i]['MONTH2']);
            moneyList.push(dataList[i]['MONEY2']);
            speedList.push(dataList[i]['SPEED2']);
            title = "累计支出";
            table_title = "累计支出";
        } else {
            monthList.push(dataList[i]['MONTH1']);
            moneyList.push(dataList[i]['MONEY1']);
            speedList.push(dataList[i]['SPEED1']);
        }
    }
    // 绘制Echart图
    drawChartNewInfo(title, "累计增速(%)", title, monthList.reverse(), speedList.reverse(), moneyList.reverse(), "亿元");

    // 组装Table
    var table_header = "<tr>" +
        "<th width='300'>月份</th>" +
        "<th width='300'>"+table_title+"(亿元)</th>" +
        "<th width=>累计增速(%)</th>" +
        "</tr>";

    $("#tableNewHeader").html(table_header);
    var table_html = "";
    for(var i = 0; i < dataList.length; i++){
        var table_html_temp = "";
        if(selType && selType == '2'){
            table_html_temp = "<tr>" +
                "<td width='300'>"+dataList[i]['MONTH2']+"</td>" +
                "<td width='300'>"+dataList[i]['MONEY2']+"</td>" +
                "<td>"+dataList[i]['SPEED2']+"</td>" +
                "</tr>";
        } else {
            table_html_temp =  "<tr>" +
                "<td width='300'>"+dataList[i]['MONTH1']+"</td>" +
                "<td width='300'>"+dataList[i]['MONEY1']+"</td>" +
                "<td>"+dataList[i]['SPEED1']+"</td>" +
                "</tr>";
        }
        table_html += table_html_temp;
    }
    $("#tableNewList").html(table_html);
}

function handleGdzctz(json, selType){
    var dataList = json.datas;
    var dateList = [];
    var upList = [];

    var title = "固定资产投资（不含农户）";
    for(var i = 0; i < dataList.length; i++){
        if(selType && selType == '2'){
            dateList.push(dataList[i]['DATA_YEAR_MONTH2']);
            upList.push(dataList[i]['DATA_UP2']);
            title = "国有及国有控股投资";
        } else {
            dateList.push(dataList[i]['DATA_YEAR_MONTH1']);
            upList.push(dataList[i]['DATA_UP1']);
            title = "固定资产投资（不含农户）";
        }
    }
    // 绘制Echart图
    drawChartNewInfo2(title, "累计同比增长(%)", dateList.reverse(), upList.reverse());

    // 组装Table
    var table_header = "<tr>" +
        "<th width='400'>月份</th>" +
        "<th >累计同比增长(%)</th>" +
        "</tr>";

    $("#tableNewHeader").html(table_header);
    var table_html = "";
    for(var i = 0; i < dataList.length; i++){
        var table_html_temp = "";
        if(selType && selType == '2'){
            table_html_temp = "<tr>" +
                "<td width='400'>"+dataList[i]['DATA_YEAR_MONTH2']+"</td>" +
                "<td>"+dataList[i]['DATA_UP2']+"</td>" +
                "</tr>";
        } else {
            table_html_temp =  "<tr>" +
                "<td width='400'>"+dataList[i]['DATA_YEAR_MONTH1']+"</td>" +
                "<td>"+dataList[i]['DATA_UP1']+"</td>" +
                "</tr>";
        }
        table_html += table_html_temp;
    }
    $("#tableNewList").html(table_html);
}

function handleQysczzsd(json, selType){
    var dataList = json.datas;
    var dateList = [];
    var upList = [];

    var title = "规模以上工业增加值";
    for(var i = 0; i < dataList.length; i++){
        if(selType && selType == '2'){
            dateList.push(dataList[i]['DATA_YEAR_MONTH2']);
            upList.push(dataList[i]['DATA_UP2']);
            title = "国有及国有控股企业";
        } else if(selType == '3'){
            dateList.push(dataList[i]['DATA_YEAR_MONTH3']);
            upList.push(dataList[i]['DATA_UP3']);
            title = "股份制企业";
        } else if(selType == '4'){
            dateList.push(dataList[i]['DATA_YEAR_MONTH4']);
            upList.push(dataList[i]['DATA_UP4']);
            title = "外商及港澳台商投资企业";
        } else {
            dateList.push(dataList[i]['DATA_YEAR_MONTH1']);
            upList.push(dataList[i]['DATA_UP1']);
            title = "规模以上工业增加值";
        }
    }
    // 绘制Echart图
    drawChartNewInfo2(title, "月度同比增长(%)", dateList.reverse(), upList.reverse());

    // 组装Table
    var table_header = "<tr>" +
        "<th width='400'>统计时间</th>" +
        "<th >月度同比增长（%）</th>" +
        "</tr>";

    $("#tableNewHeader").html(table_header);
    var table_html = "";
    for(var i = 0; i < dataList.length; i++){
        var table_html_temp = "";
        if(selType && selType == '2'){
            table_html_temp = "<tr>" +
                "<td width='400'>"+dataList[i]['DATA_YEAR_MONTH2']+"</td>" +
                "<td>"+dataList[i]['DATA_UP2']+"</td>" +
                "</tr>";
        } else if(selType == '3'){
            table_html_temp = "<tr>" +
                "<td width='400'>"+dataList[i]['DATA_YEAR_MONTH3']+"</td>" +
                "<td>"+dataList[i]['DATA_UP3']+"</td>" +
                "</tr>";
        } else if(selType == '4'){
            table_html_temp = "<tr>" +
                "<td width='400'>"+dataList[i]['DATA_YEAR_MONTH4']+"</td>" +
                "<td>"+dataList[i]['DATA_UP4']+"</td>" +
                "</tr>";
        }  else {
            table_html_temp =  "<tr>" +
                "<td width='400'>"+dataList[i]['DATA_YEAR_MONTH1']+"</td>" +
                "<td>"+dataList[i]['DATA_UP1']+"</td>" +
                "</tr>";
        }
        table_html += table_html_temp;
    }
    $("#tableNewList").html(table_html);
}

function handleHbgyl(json, selType){
    var dataList = json.datas;
    var dateList = [];
    var upList = [];

    var title = "货币和准货币（M2）";
    var title2 = "货币和准货币(亿元)";
    for(var i = 0; i < dataList.length; i++){
        if(selType && selType == '2'){
            dateList.push(dataList[i]['DATA_YEAR_MONTH2']);
            upList.push(dataList[i]['DATA_UP2']);
            title = "货币（M1）";
            title2 = "货币(亿元)";
        } else if(selType == '3'){
            dateList.push(dataList[i]['DATA_YEAR_MONTH3']);
            upList.push(dataList[i]['DATA_UP3']);
            title = "流通中货币（M0）";
            title2 = "流通中货币(亿元)";
        }else {
            dateList.push(dataList[i]['DATA_YEAR_MONTH1']);
            upList.push(dataList[i]['DATA_UP1']);
            title = "货币和准货币（M2）";
            title2 = "货币和准货币(亿元)";
        }
    }
    // 绘制Echart图
    drawChartNewInfo2(title, title2, dateList.reverse(), upList.reverse());

    // 组装Table
    var table_header = "<tr>" +
        "<th width='400'>统计时间</th>" +
        "<th >"+title2+"</th>" +
        "</tr>";

    $("#tableNewHeader").html(table_header);
    var table_html = "";
    for(var i = 0; i < dataList.length; i++){
        var table_html_temp = "";
        if(selType && selType == '2'){
            table_html_temp = "<tr>" +
                "<td width='400'>"+dataList[i]['DATA_YEAR_MONTH2']+"</td>" +
                "<td>"+dataList[i]['DATA_UP2']+"</td>" +
                "</tr>";
        } else if(selType == '3'){
            table_html_temp = "<tr>" +
                "<td width='400'>"+dataList[i]['DATA_YEAR_MONTH3']+"</td>" +
                "<td>"+dataList[i]['DATA_UP3']+"</td>" +
                "</tr>";
        }else {
            table_html_temp =  "<tr>" +
                "<td width='400'>"+dataList[i]['DATA_YEAR_MONTH1']+"</td>" +
                "<td>"+dataList[i]['DATA_UP1']+"</td>" +
                "</tr>";
        }
        table_html += table_html_temp;
    }
    $("#tableNewList").html(table_html);
}

function handleGnsczz(json, selType){
    var dataList = json.datas;
    var dateList = [];
    var numList = [];
    var upList = [];

    var title = "GDP";
    for(var i = 0; i < dataList.length; i++){
        var data_type = dataList[i]['DATA_TYPE'];
        dateList.push(dataList[i]['DATA_YEAR_MONTH']);
        numList.push(dataList[i]['DATA_NUM']);
        upList.push(dataList[i]['DATA_UP']);
        title = data_type;
    }

    // 绘制Echart图
    drawChartNewInfo(title, "比上年同期增长(%)","绝对额", dateList.reverse(), upList.reverse(), numList.reverse(), "亿元");

    // 组装Table
    var table_header = "<tr>" +
        "<th width='300'>时间</th>" +
        "<th width='300'>绝对额（亿元）</th>" +
        "<th width=>比上年同期增长（%）</th>" +
        "</tr>";

    $("#tableNewHeader").html(table_header);
    var table_html = "";
    for(var i = 0; i < dataList.length; i++){
        var table_html_temp = "";
        table_html_temp =  "<tr>" +
            "<td width='300'>"+dataList[i]['DATA_YEAR_MONTH']+"</td>" +
            "<td width='300'>"+dataList[i]['DATA_NUM']+"</td>" +
            "<td>"+dataList[i]['DATA_UP']+"</td>" +
            "</tr>";
        table_html += table_html_temp;
    }
    $("#tableNewList").html(table_html);
}

function handleShxfplsze(json, selType){
    var dataList = json.datas;
    var dateList = [];
    var numList = [];
    var upList = [];

    var title = "社会消费品零售总额主要数据（社会消费品零售总额）";
    for(var i = 0; i < dataList.length; i++){
        var data_type = dataList[i]['DATA_TYPE'];
        dateList.push(dataList[i]['DATA_YEAR_MONTH']);
        numList.push(dataList[i]['DATA_NUM']);
        upList.push(dataList[i]['DATA_UP']);
        title = data_type;
    }

    // 绘制Echart图
    drawChartNewInfo(title, "同比增长（%）","绝对量", dateList.reverse(), upList.reverse(), numList.reverse(), "亿元");

    // 组装Table
    var table_header = "<tr>" +
        "<th width='300'>时间</th>" +
        "<th width='300'>绝对量（亿元）</th>" +
        "<th width=>同比增长（%）</th>" +
        "</tr>";

    $("#tableNewHeader").html(table_header);
    var table_html = "";
    for(var i = 0; i < dataList.length; i++){
        var table_html_temp = "";
        table_html_temp =  "<tr>" +
            "<td width='300'>"+dataList[i]['DATA_YEAR_MONTH']+"</td>" +
            "<td width='300'>"+dataList[i]['DATA_NUM']+"</td>" +
            "<td>"+dataList[i]['DATA_UP']+"</td>" +
            "</tr>";
        table_html += table_html_temp;
    }
    $("#tableNewList").html(table_html);
}

function handleShxfplsze2(json, selType){
    var dataList = json.datas;
    var dateList = [];
    var numList = [];
    var upList = [];

    var title = "限额以上单位商品零售";
    for(var i = 0; i < dataList.length; i++){
        var data_type = dataList[i]['DATA_TYPE'];
        dateList.push(dataList[i]['DATA_YEAR_MONTH']);
        numList.push(dataList[i]['DATA_NUM']);
        upList.push(dataList[i]['DATA_UP']);
        title = data_type;
    }

    // 绘制Echart图
    drawChartNewInfo(title, "同比增长（%）","绝对量", dateList.reverse(), upList.reverse(), numList.reverse(), "亿元");

    // 组装Table
    var table_header = "<tr>" +
        "<th width='300'>时间</th>" +
        "<th width='300'>绝对量（亿元）</th>" +
        "<th width=>同比增长（%）</th>" +
        "</tr>";

    $("#tableNewHeader").html(table_header);
    var table_html = "";
    for(var i = 0; i < dataList.length; i++){
        var table_html_temp = "";
        table_html_temp =  "<tr>" +
            "<td width='300'>"+dataList[i]['DATA_YEAR_MONTH']+"</td>" +
            "<td width='300'>"+dataList[i]['DATA_NUM']+"</td>" +
            "<td>"+dataList[i]['DATA_UP']+"</td>" +
            "</tr>";
        table_html += table_html_temp;
    }
    $("#tableNewList").html(table_html);
}

function handleQgdzswjye(json,selType){
    var title = json.title;
    var unit = json.unit;
    var dataList = json.datas;
    var dateArr = [];
    var dataArr = [];
    var dataArr2 = [];
    for(var i = 0; i < dataList.length; i++){
        dateArr.push(dataList[i]['DATA_YEAR_STR']);
        dataArr.push(dataList[i]['DATA_SCALE']);
        dataArr2.push(dataList[i]['DATA_ABS']);
    }

    // 绘制Echart图
    drawChartNewInfo(title, "同比(%)", "绝对值", dateArr.reverse(), dataArr.reverse(), dataArr2.reverse(), unit);

    // 组装Table
    var table_header = "<tr>" +
        "<th width='300'>时间</th>" +
        "<th width='300'>绝对值(万亿元)</th>" +
        "<th width=>同比(%)</th>" +
        "</tr>";

    $("#tableNewHeader").html(table_header);
    var table_html = "";
    for(var i = 0; i < dataList.length; i++){
        var table_html_temp = "";
        table_html_temp = "<tr>" +
            "<td width='300'>"+dataList[i]['DATA_YEAR_STR']+"</td>" +
            "<td width='300'>"+dataList[i]['DATA_ABS']+"</td>" +
            "<td>"+dataList[i]['DATA_SCALE']+"</td>" +
            "</tr>";
        table_html += table_html_temp;
    }
    $("#tableNewList").html(table_html);
}

function handleQgwslse(json,selType){
    var title = json.title;
    var dataList = json.datas;
    var dateArr = [];
    var dataArr = [];
    var dataArr2 = [];
    for(var i = 0; i < dataList.length; i++){
        dateArr.push(dataList[i]['DATA_YEAR_STR']);
        dataArr.push(dataList[i]['DATA_SCALE']);
        dataArr2.push(dataList[i]['DATA_ABS']);
    }

    // 绘制Echart图
    drawChartNewInfo(title, "同比(%)", "绝对值", dateArr.reverse(), dataArr.reverse(), dataArr2.reverse(), "亿元");

    // 组装Table
    var table_header = "<tr>" +
        "<th width='300'>时间</th>" +
        "<th width='300'>绝对值(亿元)</th>" +
        "<th width=>同比(%)</th>" +
        "</tr>";

    $("#tableNewHeader").html(table_header);
    var table_html = "";
    for(var i = 0; i < dataList.length; i++){
        var table_html_temp = "";
        table_html_temp = "<tr>" +
            "<td width='300'>"+dataList[i]['DATA_YEAR_STR']+"</td>" +
            "<td width='300'>"+dataList[i]['DATA_ABS']+"</td>" +
            "<td>"+dataList[i]['DATA_SCALE']+"</td>" +
            "</tr>";
        table_html += table_html_temp;
    }
    $("#tableNewList").html(table_html);
}

// 商品零售（20251226新增）
function handleSpls(json, selType){
    var dataList = json.datas;
    var monthList = [];
    var moneyList = [];
    var speedList = [];
    var title = "商品零售（当期）";
    var table_title = "当期值";
    for(var i = 0; i < dataList.length; i++){
        if(selType && selType == '2'){
            monthList.push(dataList[i]['MONTH2']);
            moneyList.push(dataList[i]['MONEY2']);
            speedList.push(dataList[i]['SPEED2']);
            title = "商品零售（累计）";
            table_title = "累计值";
        } else {
            monthList.push(dataList[i]['MONTH1']);
            moneyList.push(dataList[i]['MONEY1']);
            speedList.push(dataList[i]['SPEED1']);
        }
    }
    // 绘制Echart图
    drawChartNewInfo(title, "增速(%)", title, monthList.reverse(), speedList.reverse(), moneyList.reverse(), "亿元");

    // 组装Table
    var table_header = "<tr>" +
        "<th width='300'>月份</th>" +
        "<th width='300'>"+table_title+"(亿元)</th>" +
        "<th width=>增速(%)</th>" +
        "</tr>";

    $("#tableNewHeader").html(table_header);
    var table_html = "";
    for(var i = 0; i < dataList.length; i++){
        var table_html_temp = "";
        if(selType && selType == '2'){
            var money2 = dataList[i]['MONEY2'] == 'null' || dataList[i]['MONEY2'] == null  ? '-' : dataList[i]['MONEY2'];
            var speed2 = dataList[i]['SPEED2'] == 'null' || dataList[i]['SPEED2'] == null  ? '-' : dataList[i]['SPEED2'];
            table_html_temp = "<tr>" +
                "<td width='300'>"+dataList[i]['MONTH2']+"</td>" +
                "<td width='300'>"+money2+"</td>" +
                "<td>"+speed2+"</td>" +
                "</tr>";
        } else {
            var money1 = dataList[i]['MONEY1'] == 'null' || dataList[i]['MONEY1'] == null ? '-' : dataList[i]['MONEY1'];
            var speed1 = dataList[i]['SPEED1'] == 'null' || dataList[i]['SPEED1'] == null ? '-' : dataList[i]['SPEED1'];
            table_html_temp =  "<tr>" +
                "<td width='300'>"+dataList[i]['MONTH1']+"</td>" +
                "<td width='300'>"+money1+"</td>" +
                "<td>"+speed1+"</td>" +
                "</tr>";
        }
        table_html += table_html_temp;
    }
    $("#tableNewList").html(table_html);
}

// 线上餐饮收入（20251226新增）
function handleXscysr(json, selType){
    var dataList = json.datas;
    var monthList = [];
    var moneyList = [];
    var speedList = [];
    var title = "限上餐饮收入(当期)";
    var table_title = "当期收入";
    for(var i = 0; i < dataList.length; i++){
        if(selType && selType == '2'){
            monthList.push(dataList[i]['MONTH2']);
            moneyList.push(dataList[i]['MONEY2']);
            speedList.push(dataList[i]['SPEED2']);
            title = "限上餐饮收入(累计)";
            table_title = "累计收入";
        } else {
            monthList.push(dataList[i]['MONTH1']);
            moneyList.push(dataList[i]['MONEY1']);
            speedList.push(dataList[i]['SPEED1']);
        }
    }
    // 绘制Echart图
    drawChartNewInfo(title, "同比增长(%)", title, monthList.reverse(), speedList.reverse(), moneyList.reverse(), "亿元");

    // 组装Table
    var table_header = "<tr>" +
        "<th width='300'>月份</th>" +
        "<th width='300'>"+table_title+"(亿元)</th>" +
        "<th width=>同比增长(%)</th>" +
        "</tr>";

    $("#tableNewHeader").html(table_header);
    var table_html = "";
    for(var i = 0; i < dataList.length; i++){
        var table_html_temp = "";
        if(selType && selType == '2'){
            var money2 = dataList[i]['MONEY2'] == 'null' || dataList[i]['MONEY2'] == null  ? '-' : dataList[i]['MONEY2'];
            var speed2 = dataList[i]['SPEED2'] == 'null' || dataList[i]['SPEED2'] == null  ? '-' : dataList[i]['SPEED2'];
            table_html_temp = "<tr>" +
                "<td width='300'>"+dataList[i]['MONTH2']+"</td>" +
                "<td width='300'>"+money2+"</td>" +
                "<td>"+speed2+"</td>" +
                "</tr>";
        } else {
            var money1 = dataList[i]['MONEY1'] == 'null' || dataList[i]['MONEY1'] == null ? '-' : dataList[i]['MONEY1'];
            var speed1 = dataList[i]['SPEED1'] == 'null' || dataList[i]['SPEED1'] == null ? '-' : dataList[i]['SPEED1'];
            table_html_temp =  "<tr>" +
                "<td width='300'>"+dataList[i]['MONTH1']+"</td>" +
                "<td width='300'>"+money1+"</td>" +
                "<td>"+speed1+"</td>" +
                "</tr>";
        }
        table_html += table_html_temp;
    }
    $("#tableNewList").html(table_html);
}

// 国内旅游年度（20251226新增）
function handleGnly(json, selType){
    var dataList = json.datas;
    var monthList = [];
    var numList = [];
    var title = "游客数量";
    var table_title = "游客数量(百万人次)";
    var unit = "百万人次";

    for(var i = 0; i < dataList.length; i++){
        if(selType && selType == '3'){
            monthList.push(dataList[i]['DATA_YEAR_MONTH3']);
            numList.push(dataList[i]['DATA_NUM3']);
            title = "人均花费";
            table_title = "人均花费(元)";
            unit = "元";
        } else if(selType == '2'){
            monthList.push(dataList[i]['DATA_YEAR_MONTH2']);
            numList.push(dataList[i]['DATA_NUM2']);
            title = "旅游花费";
            table_title = "旅游花费(亿元)";
            unit = "亿元";
        } else {
            monthList.push(dataList[i]['DATA_YEAR_MONTH1']);
            numList.push(dataList[i]['DATA_NUM1']);
            table_title = "游客数量(百万人次)";
        }
    }
    // 绘制Echart图
    drawChartNewInfo2(title, "单位：" + unit, monthList.reverse(), numList.reverse())

    // 组装Table
    var table_header = "<tr>" +
        "<th width='300'>年份</th>" +
        "<th>"+table_title+"</th>" +
        "</tr>";

    $("#tableNewHeader").html(table_header);
    var table_html = "";
    for(var i = 0; i < dataList.length; i++){
        var table_html_temp = "";
        if(selType && selType == '3'){
            var data_num3 = dataList[i]['DATA_NUM3'] == 'null' || dataList[i]['DATA_NUM3'] == null  ? '-' : dataList[i]['DATA_NUM3'];
            table_html_temp = "<tr>" +
                "<td width='300'>"+dataList[i]['DATA_YEAR_MONTH3']+"</td>" +
                "<td>"+data_num3+"</td>" +
                "</tr>";
        } else if(selType == '2') {
            var data_num2 = dataList[i]['DATA_NUM2'] == 'null' || dataList[i]['DATA_NUM2'] == null  ? '-' : dataList[i]['DATA_NUM2'];
            table_html_temp = "<tr>" +
                "<td width='300'>"+dataList[i]['DATA_YEAR_MONTH2']+"</td>" +
                "<td>"+data_num2+"</td>" +
                "</tr>";
        } else {
            var data_num1 = dataList[i]['DATA_NUM1'] == 'null' || dataList[i]['DATA_NUM1'] == null  ? '-' : dataList[i]['DATA_NUM1'];
            table_html_temp = "<tr>" +
                "<td width='300'>"+dataList[i]['DATA_YEAR_MONTH1']+"</td>" +
                "<td>"+data_num1+"</td>" +
                "</tr>";
        }
        table_html += table_html_temp;
    }
    $("#tableNewList").html(table_html);
}

function drawChartNewInfo(title, yTitle1, yTitle2, dateArr, dataArr, dataArr2, unit) {
    var optionNewInfo = {
        title : {
            left: 'center',
            text : title,
            top : 5
        },
        tooltip : {
            trigger: 'axis',
            axisPointer : {            // 坐标轴指示器，坐标轴触发有效
                type : 'shadow'        // 默认为直线，可选为：'line' | 'shadow'
            }
        },
        legend: {
            data:[yTitle1, yTitle2],
            top:35
        },
        grid: {
            left: '3%',
            right: '4%',
            bottom: '15%',
            containLabel: true
        },
        xAxis : [
            {
                axisLabel: {
                    //interval:0,
                    rotate:60
                },
                type : 'category',
                data : dateArr
            }
        ],
        yAxis : [
            {
                type : 'value',
                name : yTitle2 + "("+unit+")",
                splitLine:{
                    show:false
                }
            },
            {
                type: 'value',
                name: yTitle1,
                splitLine:{
                    show:false
                }
            }
        ],
        dataZoom: [{
            type: 'inside',
            start: 60,
            end: 100,
            bottom:0
        }, {
            start: 60,
            end: 100,
            bottom:10,
            handleIcon: 'M10.7,11.9v-1.3H9.3v1.3c-4.9,0.3-8.8,4.4-8.8,9.4c0,5,3.9,9.1,8.8,9.4v1.3h1.3v-1.3c4.9-0.3,8.8-4.4,8.8-9.4C19.5,16.3,15.6,12.2,10.7,11.9z M13.3,24.4H6.7V23h6.6V24.4z M13.3,19.6H6.7v-1.4h6.6V19.6z',
            handleSize: '80%',
            handleStyle: {
                color: '#fff',
                shadowBlur: 3,
                shadowColor: 'rgba(0, 0, 0, 0.6)',
                shadowOffsetX: 2,
                shadowOffsetY: 2
            }
        }],
        series : [
            {
                name:yTitle2,
                type:'bar',
                barWidth : 20,
                color:'#ff7575',
                stack: 'aa',
                data: dataArr2
            },
            {
                name: yTitle1,
                type:'line',
                yAxisIndex: 1,
                color:'#be77ff',
                data: dataArr
            }
        ]
    };

    new drawCharts({ elem: 'mapBoxNew', option: optionNewInfo, theme: null }).init();
}

function drawChartNewInfo2(title, yTitle, dateArr, dataArr) {
    var optionNewInfo = {
        title : { left: 'center', text : title, top : 5},
        tooltip : { trigger: 'axis', axisPointer: {type : 'shadow'} },
        legend: { data:[yTitle], top:35},
        grid: {left: '3%', right: '4%', bottom: '15%', containLabel: true},
        xAxis : [{
            axisLabel: {rotate:60},
            type : 'category',
            data : dateArr
        }],
        yAxis : [{
            type : 'value',
            name : yTitle,
            splitLine:{show:false}
        }],
        dataZoom: [{type: 'inside',start: 30,end: 100,bottom:0},{
            start: 0,
            end: 100,
            bottom:10,
            handleIcon: 'M10.7,11.9v-1.3H9.3v1.3c-4.9,0.3-8.8,4.4-8.8,9.4c0,5,3.9,9.1,8.8,9.4v1.3h1.3v-1.3c4.9-0.3,8.8-4.4,8.8-9.4C19.5,16.3,15.6,12.2,10.7,11.9z M13.3,24.4H6.7V23h6.6V24.4z M13.3,19.6H6.7v-1.4h6.6V19.6z',
            handleSize: '80%',
            handleStyle: {
                color: '#fff',
                shadowBlur: 3,
                shadowColor: 'rgba(0, 0, 0, 0.6)',
                shadowOffsetX: 2,
                shadowOffsetY: 2
            }
        }],
        series : [{
            name:yTitle,
            type:'bar',
            barWidth : 20,
            color:'#ff7575',
            stack: 'aa',
            data: dataArr
        }]
    };
    new drawCharts({ elem: 'mapBoxNew', option: optionNewInfo, theme: null }).init();
}

function show_select_type_box(current_sel){
    if(current_sel && (current_sel == 'qgdzswjyejzs' || current_sel == 'qgwslsejzs')){
        $("#select_type_box_id").html('');
        $("#select_type_box_id").hide();
    } else {
        init_select_type_box(current_sel);
        $("#select_type_box_id").show();
    }
}

function init_select_type_box(current_sel) {
    selectHtml = "<div class='bd f-cb'><div class='tit' style='padding-left:10px;display: flex;'><div style='width: 85px;'>品种选择：</div>" +
        "<div><label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
        "<input type='radio' name='czszRadio' title='累计收入' data-url='czsr' value='1' onchange='loadNewData(1)' checked='checked'>累计收入</label>" +
        "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
        "<input type='radio' name='czszRadio' title='累计支出' data-url='czsr' value='2' onchange='loadNewData(2)'>累计支出</label>" +
        "</div></div></div>";
    if(current_sel && current_sel == 'gdzctz'){
        selectHtml = "<div class='bd f-cb'><div class='tit' style='padding-left:10px;display: flex;'><div style='width: 85px'>品种选择：</div>" +
            "<div><label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='固定资产投资（不含农户）' data-url='czsr' value='1' onchange='loadNewData(1)' checked='checked'>固定资产投资（不含农户）</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='国有及国有控股公司' data-url='czsr' value='2' onchange='loadNewData(2)'>国有及国有控股公司</label>" +
            "</div></div></div>";
    }else if (current_sel == 'gysczzsd') {
        selectHtml = "<div class='bd f-cb'><div class='tit' style='padding-left:10px;display: flex;'><div style='width: 85px;'>品种选择：</div>" +
            "<div><label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:25px;'>" +
            "<input type='radio' name='czszRadio' title='规模以上工业增加值' data-url='czsr' value='1' onchange='loadNewData(1)' checked='checked'>规模以上工业增加值</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:25px;'>" +
            "<input type='radio' name='czszRadio' title='国有及国有控股企业' data-url='czsr' value='2' onchange='loadNewData(2)'>国有及国有控股企业</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:25px;'>" +
            "<input type='radio' name='czszRadio' title='股份制企业' data-url='czsr' value='3' onchange='loadNewData(3)' >股份制企业</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:25px;'>" +
            "<input type='radio' name='czszRadio' title='外商及港澳台商投资企业' data-url='czsr' value='4' onchange='loadNewData(4)'>外商及港澳台商投资企业</label>" +
            "</div></div></div>";
    }else if (current_sel == 'hbgyl') {
        selectHtml = "<div class='bd f-cb'><div class='tit' style='padding-left:10px;display: flex;'><div style='width: 85px;'>品种选择：</div>" +
            "<div><label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='货币和准货币（M2）' data-url='czsr' value='1' onchange='loadNewData(1)' checked='checked'>货币和准货币（M2）</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='货币（M1）' data-url='czsr' value='2' onchange='loadNewData(2)'>货币（M1）</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='流通中货币（M0）' data-url='czsr' value='3' onchange='loadNewData(3)' >流通中货币（M0）</label>" +
            "</div></div></div>";
    }else if (current_sel == 'gnsczz') {
        selectHtml = "<div class='bd f-cb'><div class='tit' style='padding-left:10px;display: flex;'><div style='width: 22%;'>品种选择：</div>" +
            "<div><label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='GDP' data-url='czsr' value='GDP' onchange='loadNewData(1)' checked='checked'>GDP</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='第一产业' data-url='czsr' value='第一产业' onchange='loadNewData(2)'>第一产业</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='第二产业' data-url='czsr' value='第二产业' onchange='loadNewData(3)' >第二产业</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='第三产业' data-url='czsr' value='第三产业' onchange='loadNewData(4)' >第三产业</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='农林牧渔业' data-url='czsr' value='农林牧渔业' onchange='loadNewData(5)'>农林牧渔业</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='工业' data-url='czsr' value='工业' onchange='loadNewData(6)'>工业</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='制造业' data-url='czsr' value='制造业' onchange='loadNewData(7)' >制造业</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='建筑业' data-url='czsr' value='建筑业' onchange='loadNewData(8)' >建筑业</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='批发和零售业' data-url='czsr' value='批发和零售业' onchange='loadNewData(9)'>批发和零售业</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='交通运输、仓储和邮政业' data-url='czsr' value='交通运输、仓储和邮政业' onchange='loadNewData(10)'>交通运输、仓储和邮政业</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='住宿和餐饮业' data-url='czsr' value='住宿和餐饮业' onchange='loadNewData(11)' >住宿和餐饮业</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='金融业' data-url='czsr' value='金融业' onchange='loadNewData(12)' >金融业</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='房地产业' data-url='czsr' value='房地产业' onchange='loadNewData(13)'>房地产业</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='信息传输、软件和信息技术服务业' data-url='czsr' value='信息传输、软件和信息技术服务业' onchange='loadNewData(14)'>信息传输、软件和信息技术服务业</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='租赁和商务服务业' data-url='czsr' value='租赁和商务服务业' onchange='loadNewData(15)' >租赁和商务服务业</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='其他行业' data-url='czsr' value='其他行业' onchange='loadNewData(16)' >其他行业</label>" +
            "</div></div></div>";
    } else if (current_sel == 'shxfplsze') {
        selectHtml = "<div class='bd f-cb'><div class='tit' style='padding-left:10px;display: flex;'><div style='width: 80px;'>品种选择：</div>" +
            "<div><label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:25px;'>" +
            "<input type='radio' name='czszRadio' title='社会消费品零售总额' data-url='czsr' value='社会消费品零售总额' onchange='loadNewData(1)' checked='checked'>社会消费品零售总额</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:25px;'>" +
            "<input type='radio' name='czszRadio' title='按经营地分(城镇)' data-url='czsr' value='按经营地分(城镇)' onchange='loadNewData(2)'>按经营地分(城镇)</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:25px;'>" +
            "<input type='radio' name='czszRadio' title='按经营地分(乡村)' data-url='czsr' value='按经营地分(乡村)' onchange='loadNewData(3)' >按经营地分(乡村)</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:25px;'>" +
            "<input type='radio' name='czszRadio' title='按消费类型分(餐饮收入)' data-url='czsr' value='按消费类型分(餐饮收入)' onchange='loadNewData(4)' >按消费类型分(餐饮收入)</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:25px;'>" +
            "<input type='radio' name='czszRadio' title='按消费类型分(商品零售)' data-url='czsr' value='按消费类型分(商品零售)' onchange='loadNewData(5)'>按消费类型分(商品零售)</label>" +
            "</div></div></div>";
    } else if (current_sel == 'shxfplsze2') {
        selectHtml = "<div class='bd f-cb'><div class='tit' style='padding-left:10px;display: flex;'><div style='width: 22%;'>品种选择：</div>" +
            "<div><label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='限额以上单位商品零售' data-url='czsr' value='限额以上单位商品零售' onchange='loadNewData(1)' checked='checked'>限额以上单位商品零售</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='粮油、食品类' data-url='czsr' value='粮油、食品类' onchange='loadNewData(2)'>粮油、食品类</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='饮料类' data-url='czsr' value='饮料类' onchange='loadNewData(3)' >饮料类</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='烟酒类' data-url='czsr' value='烟酒类' onchange='loadNewData(4)' >烟酒类</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='服装、鞋帽、针纺织品类' data-url='czsr' value='服装、鞋帽、针纺织品类' onchange='loadNewData(5)'>服装、鞋帽、针纺织品类</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='化妆品类' data-url='czsr' value='化妆品类' onchange='loadNewData(6)'>化妆品类</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='金银珠宝类' data-url='czsr' value='金银珠宝类' onchange='loadNewData(7)'>金银珠宝类</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='日用品类' data-url='czsr' value='日用品类' onchange='loadNewData(8)' >日用品类</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='家用电器和音像器材类' data-url='czsr' value='家用电器和音像器材类' onchange='loadNewData(9)' >家用电器和音像器材类</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='中西药品类' data-url='czsr' value='中西药品类' onchange='loadNewData(10)'>中西药品类</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='文化办公用品类' data-url='czsr' value='文化办公用品类' onchange='loadNewData(11)'>文化办公用品类</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='家具类' data-url='czsr' value='家具类' onchange='loadNewData(12)'>家具类</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='通讯器材类' data-url='czsr' value='通讯器材类' onchange='loadNewData(13)' >通讯器材类</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='石油及制品类' data-url='czsr' value='石油及制品类' onchange='loadNewData(14)' >石油及制品类</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='汽车类' data-url='czsr' value='汽车类' onchange='loadNewData(15)'>汽车类</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='建筑及装潢材料类' data-url='czsr' value='建筑及装潢材料类' onchange='loadNewData(16)'>建筑及装潢材料类</label>" +
            "</div></div></div>";
    } else if (current_sel == 'spls') {
        selectHtml = "<div class='bd f-cb'><div class='tit' style='padding-left:10px;display: flex;'><div style='width: 85px;'>品种选择：</div>" +
            "<div><label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='商品零售(当期)' data-url='czsr' value='1' onchange='loadNewData(1)' checked='checked'>商品零售(当期)</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='商品零售(累计)' data-url='czsr' value='2' onchange='loadNewData(2)'>商品零售(累计)</label>" +
            "</div></div></div>";
    } else if (current_sel == 'xscysr') {
        selectHtml = "<div class='bd f-cb'><div class='tit' style='padding-left:10px;display: flex;'><div style='width: 85px;'>品种选择：</div>" +
            "<div><label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='限上餐饮收入(当期)' data-url='czsr' value='1' onchange='loadNewData(1)' checked='checked'>限上餐饮收入(当期)</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='限上餐饮收入(累计)' data-url='czsr' value='2' onchange='loadNewData(2)'>限上餐饮收入(累计)</label>" +
            "</div></div></div>";
    } else if (current_sel == 'gnly') {
        selectHtml = "<div class='bd f-cb'><div class='tit' style='padding-left:10px;display: flex;'><div style='width: 85px;'>品种选择：</div>" +
            "<div><label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='游客数量' data-url='czsr' value='1' onchange='loadNewData(1)' checked='checked'>游客数量</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='旅游花费' data-url='czsr' value='2' onchange='loadNewData(2)'>旅游花费</label>" +
            "<label style='padding-left:10px;display:inline-block;font-size:14px;margin-right:30px;'>" +
            "<input type='radio' name='czszRadio' title='人均花费' data-url='czsr' value='2' onchange='loadNewData(3)'>人均花费</label>" +
            "</div></div></div>";
    }
    $("#select_type_box_id").html(selectHtml);
}
/**
 * =========================== 非结构化数据 End================================
 */
