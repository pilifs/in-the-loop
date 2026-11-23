public final class StringReplay {
    public static void main(String[] args) throws Exception {
        String s=null;
        if(!args[2].equals("null")) {
            var text=new StringBuilder();
            if(!args[2].isEmpty())for(String u:args[2].split(","))text.append((char)Integer.parseInt(u));
            s=text.toString();
        }
        try{System.out.println("returned "+Class.forName(args[0]).getMethod(args[1],String.class).invoke(null,s));}
        catch(java.lang.reflect.InvocationTargetException e){System.out.println("escaped "+e.getCause().getClass().getName());}
    }
}
