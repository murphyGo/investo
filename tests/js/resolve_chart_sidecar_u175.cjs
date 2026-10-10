const {harness}=require('./chart_harness.cjs');
(async()=>{
  const h=harness({url:process.argv[2],src:process.argv[3]});
  await h.toggle();
  console.log(JSON.stringify({url:h.requests[0].url,requests:h.requests.length,charts:h.charts.length}));
})().catch(error=>{console.error(error);process.exitCode=1;});
