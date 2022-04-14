#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

int main( int argc, char *argv[] ) {
    int id = 0;
    if  (argc == 1) {
        id = getuid();
    }
    else {
        id += atoi(argv[1]);
    }
    printf("%d\n",id);

    printf("%d\n", geteuid());
    seteuid( id );
    printf("%d\n", geteuid());

    return 0;
}
