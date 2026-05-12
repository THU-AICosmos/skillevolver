package clusterdata.query;

import clusterdata.utils.AppBase;
import org.apache.flink.api.java.utils.ParameterTool;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;

public class BusiestBurstPerKilledJob extends AppBase {

    public static void main(String[] args) throws Exception {

        ParameterTool params = ParameterTool.fromArgs(args);
        String taskInput = params.get("task_input", null);
        String jobInput = params.get("job_input", null);
        String outputPath = params.get("output", null);
        System.out.println("task_input  "+taskInput);
        System.out.println("job_input  "+jobInput);
        final int burstgap = params.getInt("burstgap", 300);

        // set up streaming execution environment
        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();



        env.execute("BusiestBurstPerKilledJob");
    }

}
