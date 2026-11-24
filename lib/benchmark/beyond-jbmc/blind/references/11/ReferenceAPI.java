import com.headius.options.BooleanOption;
public final class ReferenceAPI {
    enum Group { SAMPLE }
    public static long primary(int n) {
        String key="campaign.numbered.option.example",prior=System.getProperty(key);
        try {
            if(n==3)System.clearProperty(key);else System.setProperty(key,n==0?"":n==1?"true":"false");
            return new BooleanOption(key,Group.SAMPLE,false,"campaign check").reload()?1:0;
        } finally {if(prior==null)System.clearProperty(key);else System.setProperty(key,prior);}
    }
    public static long control(int n) {return new BooleanOption("campaign.numbered.option.control",Group.SAMPLE,true,"independent").reload()?1:0;}
}
